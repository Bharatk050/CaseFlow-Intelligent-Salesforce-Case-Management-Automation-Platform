from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from io import BytesIO

from openpyxl import Workbook
from test_access import environment, session, ticket, main, salesforce, ORG, CASE_A


def test_resolution_transitions_and_reconnection(environment):
    session(environment)
    ticket()
    for status in ['resolved', 'resolved', 'open', 'resolved']:
        assert environment.patch('/tickets/LOCAL-A', json={'status': status}).status_code == 200
    result = environment.get('/me/progress?days=7').json()
    assert result['total_resolutions'] == result['period_resolutions'] == 2
    assert len(result['daily']) == 7
    assert sum(day['count'] for day in result['daily']) == 2
    environment.post('/auth/salesforce/disconnect')
    assert environment.get('/me/progress').status_code == 401
    session(environment, token='reconnected')
    assert environment.get('/me/progress').json()['total_resolutions'] == 2
    session(environment, token='other', user='user-b')
    assert environment.get('/me/progress').json()['total_resolutions'] == 0


def test_concurrent_duplicate_saves(environment):
    session(environment)
    ticket()
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: environment.patch('/tickets/LOCAL-A', json={'status': 'resolved'}), range(4)))
    assert all(result.status_code == 200 for result in results)
    assert len(main.load_ticket('LOCAL-A')['resolution_events']) == 1


def test_progress_timezone_validation_visibility_and_legacy(environment, monkeypatch):
    session(environment)
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 9, 28, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(main, 'datetime', Clock)
    event = {'at': '2026-09-27T23:30:00+00:00', 'member_id': 'user-a', 'instance_url': ORG}
    ticket(status='resolved')  # No inferred credit for legacy status.
    mirrored = main.mirror_salesforce_case({'Id': CASE_A}, ORG)
    mirrored['resolution_events'] = [event, {**event, 'member_id': 'other'}, {**event, 'instance_url': 'other'}]
    main.save_ticket(mirrored)
    monkeypatch.setattr(salesforce, 'accessible_case_ids', lambda s, ids: {CASE_A})
    result = environment.get('/me/progress?days=7&timezone=Asia/Calcutta')
    assert result.headers['cache-control'] == 'no-store'
    assert result.json()['daily'][-1] == {'date': '2026-09-28', 'count': 1}
    assert result.json()['total_resolutions'] == 1
    assert environment.get('/me/progress?timezone=UTC').json()['daily'][-2]['count'] == 1
    for query in ['days=8', 'timezone=Not/AZone']:
        assert environment.get('/me/progress?' + query).status_code == 422
    monkeypatch.setattr(salesforce, 'accessible_case_ids', lambda s, ids: set())
    assert environment.get('/me/progress').json()['total_resolutions'] == 0


def test_signed_in_excel_prefers_durable_identity(environment):
    environment.post('/auth/local-beta')
    assert environment.get('/me/progress').status_code == 401
    session(environment)
    workbook = Workbook()
    workbook.active.append(['Subject', 'Customer', 'Message'])
    workbook.active.append(['Example request', 'Synthetic', 'Please help me.'])
    content = BytesIO()
    workbook.save(content)
    imported = environment.post('/tickets/import/excel', content=content.getvalue()).json()['tickets'][0]
    assert imported['created_by'] == 'user-a'
    assert imported['salesforce_instance_url'] == ORG
    environment.patch('/tickets/' + imported['id'], json={'status': 'resolved'})
    assert environment.get('/me/progress').json()['total_resolutions'] == 1


def test_development_oauth_return_and_origin_allowlist(environment, monkeypatch):
    from urllib.parse import urlparse, parse_qs
    assert environment.get('/auth/salesforce?return_to=https://evil.example').status_code == 400
    response = environment.get('/auth/salesforce?return_to=https://localhost:5173', follow_redirects=False)
    state = parse_qs(urlparse(response.headers['location']).query)['state'][0]
    monkeypatch.setattr(salesforce, 'complete_authorization', lambda code, value: 'new-session')
    response = environment.get('/auth/salesforce/callback', params={'state': state, 'code': 'fake'}, follow_redirects=False)
    assert response.headers['location'] == 'https://localhost:5173/?salesforce=connected'
    response = environment.get('/health', headers={'origin': 'https://localhost:5173'})
    assert response.headers['access-control-allow-origin'] == 'https://localhost:5173'
    response = environment.get('/health', headers={'origin': 'https://localhost:9999'})
    assert 'access-control-allow-origin' not in response.headers
