def load_tests(loader, tests, pattern):
    return loader.loadTestsFromNames([
        'tests.test_core.CoreContract.test_path_escape_symlink_and_private_state_denied',
        'tests.test_core.CoreContract.test_review_survives_restart_and_revalidates_content',
        'tests.test_core.CoreContract.test_job_survives_engine_disconnect_and_retry_deduplicates',
        'tests.test_credentials.CredentialsTests.test_trusted_mode_still_requires_consent_and_once_cannot_replay',
        'tests.test_credentials.CredentialsTests.test_http_owner_decisions_reject_agent_and_no_secrets_in_mcp',
        'tests.test_credentials.CredentialsTests.test_always_grant_revoke_and_mapping_change',
    ])
