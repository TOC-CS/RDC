"""Regression fixtures derived from a physical SwiftUI Form hierarchy."""
import json
import unittest
from rdc.mobile import _native_tree

BOUNDS = 'x="20" y="200" width="300" height="40"'


def hierarchy(children, outer='visible="true"', collection='visible="false" accessible="false"'):
    return ('<AppiumAUT><XCUIElementTypeApplication ' + outer +
            ' x="0" y="0" width="440" height="956">'
            '<XCUIElementTypeCollectionView ' + collection +
            ' x="0" y="0" width="440" height="956">' + children +
            '</XCUIElementTypeCollectionView></XCUIElementTypeApplication></AppiumAUT>')


class CollectionVisibilityTests(unittest.TestCase):
    def test_visible_form_children_survive_nonaccessible_collection_container(self):
        tree = _native_tree(hierarchy(
            '<XCUIElementTypeOther visible="true" accessible="false">' +
            '<XCUIElementTypeButton visible="true" label="Check connection" ' + BOUNDS + '/>' +
            '<XCUIElementTypeTextField visible="true" label="PRIVATE_ORIGIN" value="PRIVATE_VALUE" ' + BOUNDS + '/>' +
            '</XCUIElementTypeOther>'), 'iOS')
        self.assertEqual(['Check connection', 'Text field'], [c['name'] for c in tree['controls']])
        self.assertTrue(tree['controls'][1]['can_fill'])
        self.assertNotIn('PRIVATE_', json.dumps(tree['controls']))
        self.assertEqual('/*[1]/*[1]/*[1]/*[1]', tree['handles']['c1']['path'])

    def test_missing_or_false_leaf_visibility_is_not_promoted(self):
        tree = _native_tree(hierarchy(
            '<XCUIElementTypeButton label="Unknown" ' + BOUNDS + '/>' +
            '<XCUIElementTypeButton visible="false" label="Hidden" ' + BOUNDS + '/>'), 'iOS')
        self.assertEqual([], tree['controls'])
        self.assertEqual('', tree['text'])

    def test_hidden_app_or_accessible_container_still_blocks_descendants(self):
        button = '<XCUIElementTypeButton visible="true" label="Hidden" ' + BOUNDS + '/>'
        for source in (hierarchy(button, outer='visible="false"'),
                       hierarchy(button, collection='visible="false" accessible="true"')):
            with self.subTest(source=source):
                self.assertEqual([], _native_tree(source, 'iOS')['controls'])

    def test_secure_descendants_and_aggregate_labels_remain_private(self):
        tree = _native_tree(hierarchy(
            '<XCUIElementTypeSecureTextField visible="true" label="PRIVATE_SECRET" value="PRIVATE_VALUE" ' + BOUNDS + '>' +
            '<XCUIElementTypeButton visible="true" label="PRIVATE_CHILD" ' + BOUNDS + '/>' +
            '</XCUIElementTypeSecureTextField>' +
            '<XCUIElementTypeButton visible="true" label="Clear session" ' + BOUNDS + '/>',
            collection='visible="false" accessible="false" label="PRIVATE_AGGREGATE"'), 'iOS')
        self.assertTrue(tree['sensitive'])
        self.assertEqual(['Secure field', 'Clear session'], [c['name'] for c in tree['controls']])
        self.assertFalse(tree['controls'][0]['can_fill'])
        self.assertNotIn('PRIVATE_', json.dumps(tree['controls']) + tree['text'])

    def test_source_wrapper_is_not_part_of_native_xpath_lookup(self):
        application = ('<XCUIElementTypeApplication visible="true">' +
                       '<XCUIElementTypeButton visible="true" label="Save" ' + BOUNDS + '/>' +
                       '</XCUIElementTypeApplication>')
        for source in (application, '<AppiumAUT>' + application + '</AppiumAUT>'):
            with self.subTest(wrapped=source.startswith('<AppiumAUT>')):
                tree = _native_tree(source, 'iOS')
                self.assertEqual('/*[1]/*[1]', tree['handles']['c1']['path'])
