"""Curated public-preview regression suite, capped and free of owner test data."""
import unittest

def load_tests(loader, tests, pattern):
    names = [
        'tests.test_mobile_command_engine.CommandEngineTests',
        'tests.test_mobile_terminal_routing.TerminalRoutingTests',
        'tests.test_mobile_app_lifecycle.AppLifecycleTests.test_open_switches_and_invalidates_old_controls',
        'tests.test_mobile_app_lifecycle.AppLifecycleTests.test_close_and_reopen',
        'tests.test_mobile_app_lifecycle.AppLifecycleTests.test_cross_device_and_endpoint_refused_before_driver',
        'tests.test_mobile_app_lifecycle.AppLifecycleTests.test_single_use_ticket_no_replay',
        'tests.test_mobile_app_lifecycle.AppLifecycleTests.test_lost_launch_response_blocks_input_until_exact_reobservation',
        'tests.test_mobile_visual_input.VisualInputTests.test_verified_frame_allows_window_anchored_two_touch_without_accessible_controls',
        'tests.test_mobile_visual_input.VisualInputTests.test_secure_field_blocks_capture',
        'tests.test_mobile_visual_input.VisualInputTests.test_changed_process_refuses_before_dispatch',
        'tests.test_mobile_visual_input.VisualInputTests.test_failed_action_releases_once_and_ticket_cannot_replay',
        'tests.test_mobile_fast_ready.FastReadyTests.test_open_ready_uses_new_app_identity',
    ]
    suite=loader.loadTestsFromNames(names)
    if suite.countTestCases()!=30: raise ValueError('Public preview allocation must equal 30')
    return suite
