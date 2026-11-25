"""Generic structural visibility regression derived from keyboard-active native UI."""
import json
import unittest
from rdc.mobile import _native_tree

FULL='x="0" y="0" width="400" height="800"'
CELL='x="10" y="110" width="380" height="50"'
HIDDEN='visible="false" enabled="true" accessible="false"'
VISIBLE='visible="true" enabled="true" accessible="false"'
FIELD='<XCUIElementTypeTextField visible="true" enabled="true" accessible="true" x="15" y="120" width="360" height="25" label="Private field label" value="SYNTHETIC_PRIVATE_VALUE"/>'
RUN='<XCUIElementTypeButton visible="true" enabled="true" accessible="true" x="10" y="165" width="380" height="50" label="Run fixture"/>'
MARKER='<XCUIElementTypeStaticText visible="true" enabled="true" accessible="true" x="10" y="50" width="380" height="40" label="Fixture heading"/>'
KEYBOARD=f'<XCUIElementTypeWindow {VISIBLE} {FULL}><XCUIElementTypeKeyboard {VISIBLE} x="0" y="500" width="400" height="300"/></XCUIElementTypeWindow>'

def fixture(*, keyboard=KEYBOARD, window=VISIBLE, hidden=HIDDEN, ancestor_bounds=FULL, children=None, extra=''):
    content=children if children is not None else FIELD+RUN+MARKER
    collection=f'<XCUIElementTypeCollectionView {hidden} {FULL}><XCUIElementTypeCell {VISIBLE} {CELL}>{content}</XCUIElementTypeCell></XCUIElementTypeCollectionView>'
    for _ in range(4):
        collection=f'<XCUIElementTypeOther {hidden} {ancestor_bounds}>{collection}</XCUIElementTypeOther>'
    return f'<AppiumAUT><XCUIElementTypeApplication {VISIBLE} {FULL}><XCUIElementTypeWindow {window} {FULL}>{collection}{extra}</XCUIElementTypeWindow>{keyboard}</XCUIElementTypeApplication></AppiumAUT>'

def tree(**kwargs):return _native_tree(fixture(**kwargs),'iOS')
def names(t):return [c['name'] for c in t['controls']]

class KeyboardVisibilityTests(unittest.TestCase):
    def test_keyboard_active_structural_chain_preserves_explicit_controls(self):
        t=tree()
        self.assertIn('Run fixture',names(t))
        self.assertIn('Fixture heading',t['text'])
        self.assertEqual(1,sum(c['can_fill'] for c in t['controls']))
        self.assertNotIn('SYNTHETIC_PRIVATE_VALUE',json.dumps(t,default=str))
        self.assertNotIn('Private field label',json.dumps(t,default=str))
        self.assertEqual(2,len(t['visual_windows']))
    def test_no_keyboard_retains_hidden_ancestor_refusal(self):
        self.assertNotIn('Run fixture',names(tree(keyboard='')))
    def test_hidden_window_remains_hidden(self):
        self.assertNotIn('Run fixture',names(tree(window=HIDDEN)))
    def test_non_fullscreen_hidden_ancestor_remains_hidden(self):
        self.assertNotIn('Run fixture',names(tree(ancestor_bounds='x="0" y="0" width="399" height="800"')))
    def test_hidden_accessible_container_remains_hidden(self):
        self.assertNotIn('Run fixture',names(tree(hidden=HIDDEN.replace('accessible="false"','accessible="true"'))))
    def test_disabled_hidden_container_remains_hidden(self):
        self.assertNotIn('Run fixture',names(tree(hidden=HIDDEN.replace('enabled="true"','enabled="false"'))))
    def test_unrelated_hidden_branch_remains_hidden(self):
        extra=f'<XCUIElementTypeOther {HIDDEN} {FULL}><XCUIElementTypeButton {VISIBLE} {CELL} label="Hidden sibling"/></XCUIElementTypeOther>'
        t=tree(extra=extra)
        self.assertNotIn('Hidden sibling',names(t))
    def test_hidden_secure_field_is_still_detected(self):
        secure=f'<XCUIElementTypeSecureTextField {HIDDEN} {CELL} value="SYNTHETIC_PASSWORD"/>'
        t=tree(children=FIELD+RUN+MARKER+secure)
        self.assertTrue(t['sensitive'])
        self.assertNotIn('SYNTHETIC_PASSWORD',json.dumps(t,default=str))
    def test_missing_leaf_visibility_remains_hidden(self):
        t=tree(children=FIELD+RUN.replace('visible="true" ','')+MARKER)
        self.assertNotIn('Run fixture',names(t))
    def test_ambiguous_keyboards_do_not_recover_hidden_chain(self):
        self.assertNotIn('Run fixture',names(tree(keyboard=KEYBOARD+KEYBOARD)))
    def test_hidden_interactive_child_remains_hidden(self):
        child=f'<XCUIElementTypeCell visible="false" enabled="true" accessible="true" {CELL}>{RUN}</XCUIElementTypeCell>'
        self.assertNotIn('Run fixture',names(tree(children=FIELD+MARKER+child)))
    def test_keyboard_under_hidden_window_does_not_admit_recovery(self):
        keyboard=KEYBOARD.replace('<XCUIElementTypeWindow visible="true"','<XCUIElementTypeWindow visible="false"',1)
        self.assertNotIn('Run fixture',names(tree(keyboard=keyboard)))
    def test_multiple_apps_do_not_admit_recovery(self):
        xml=fixture().replace('</AppiumAUT>',f'<XCUIElementTypeApplication {VISIBLE} {FULL}/></AppiumAUT>')
        self.assertNotIn('Run fixture',names(_native_tree(xml,'iOS')))
