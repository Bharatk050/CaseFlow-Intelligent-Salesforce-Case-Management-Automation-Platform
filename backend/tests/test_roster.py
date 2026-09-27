from urllib.parse import parse_qs, urlparse
import pytest
from fastapi import HTTPException
from test_access import environment, session, ticket, main, salesforce, ORG, CASE_A, CASE_B

VIEW = '00B000000000001AAA'


def mock_view(monkeypatch, *, views=None, records=None, failure=None):
    def response(url, **kwargs):
        assert kwargs['token'] == 'fake-access'
        if failure:
            raise HTTPException(502, 'Salesforce request failed. Retry.')
        if url.endswith('/listviews'):
            return {'listviews': views if views is not None else [{'id': VIEW, 'label': ' ROSTER SUPPORT QUEUE '}]}
        if '/results?' in url:
            return {'records': records if records is not None else [{'id': CASE_B}, {'id': CASE_A}], 'done': True}
        return {'records': [{'Id': CASE_A, 'Subject': 'First', 'Description': 'Full case details'}, {'Id': CASE_B, 'Subject': 'Second'}]}
    monkeypatch.setattr(salesforce, '_json_request', response)


def test_roster_preserves_order_and_resolution_history(environment, monkeypatch):
    session(environment)
    existing = main.mirror_salesforce_case({'Id': CASE_A}, ORG)
    existing['resolution_events'] = [{'at': main.now(), 'member_id': 'user-a', 'instance_url': ORG}]
    main.save_ticket(existing)
    unrelated = ticket('UNRELATED')
    mock_view(monkeypatch)
    response = environment.post('/auth/salesforce/roster-support/sync')
    assert response.status_code == 200
    data = response.json()
    assert data['state'] == 'found' and data['count'] == 2
    assert [item['salesforce_case_id'] for item in data['cases']] == [CASE_B, CASE_A]
    assert data['cases'][1]['message'] == 'Full case details'
    assert data['cases'][1]['resolution_events'] == existing['resolution_events']
    assert main.load_ticket('UNRELATED') == unrelated
    mock_view(monkeypatch, records=[])
    assert environment.post('/auth/salesforce/roster-support/sync').json()['count'] == 0
    assert main.load_ticket(existing['id'])['resolution_events'] == existing['resolution_events']


def test_roster_missing_empty_ambiguous_errors_and_auth(environment, monkeypatch):
    assert environment.post('/auth/salesforce/roster-support/sync').status_code == 401
    session(environment)
    mock_view(monkeypatch, views=[{'id': VIEW, 'label': 'My open cases'}, {'id': VIEW, 'label': 'Roster support Queue extra'}])
    assert environment.post('/auth/salesforce/roster-support/sync').json()['state'] == 'missing'
    mock_view(monkeypatch, records=[])
    assert environment.post('/auth/salesforce/roster-support/sync').json()['state'] == 'found'
    mock_view(monkeypatch, views=[{'id': VIEW, 'label': 'Roster support Queue'}, {'id': '00B000000000002AAA', 'label': 'roster support queue'}])
    assert environment.post('/auth/salesforce/roster-support/sync').status_code == 409
    mock_view(monkeypatch, failure=True)
    assert environment.post('/auth/salesforce/roster-support/sync').status_code == 502


def test_paginated_list_discovery_results_and_hydration(environment, monkeypatch):
    session(environment)
    ids = [f'500{i:012d}AAA' for i in range(2001)]
    offsets = []
    def response(url, **kwargs):
        if url.endswith('/listviews'):
            return {'listviews': [], 'nextRecordsUrl': '/services/data/v60.0/views-next'}
        if url.endswith('/views-next'):
            return {'listviews': [{'id': VIEW, 'label': 'Roster support Queue'}]}
        params = parse_qs(urlparse(url).query)
        if '/results?' in url:
            offset = int(params['offset'][0]); offsets.append(offset)
            return {'records': [{'columns': [{'fieldNameOrPath': 'Id', 'value': value}]} for value in ids[offset:offset + 2000]]}
        selected = params['q'][0].split('IN (')[1].rstrip(')').replace("'", '').split(',')
        return {'records': [{'Id': value} for value in reversed(selected)]}
    monkeypatch.setattr(salesforce, '_json_request', response)
    view, cases = salesforce.roster_support_cases(salesforce._session('session-a'))
    assert view['id'] == VIEW and offsets == [0, 2000]
    assert [case['Id'] for case in cases] == ids


def test_name_backfill_cached_and_activity_attributed(environment, monkeypatch):
    user = '005000000000001AAA'
    session(environment, user=user)
    calls = []
    def response(url, **kwargs):
        calls.append(url)
        return {'Name': 'Alex Rivera'}
    monkeypatch.setattr(salesforce, '_json_request', response)
    assert environment.get('/team/members').json()[0] == {'id': user, 'name': 'Alex Rivera', 'role': 'Support agent'}
    assert environment.get('/team/members').json()[0]['name'] == 'Alex Rivera'
    assert len(calls) == 1
    ticket(created_by=user)
    item = environment.patch('/tickets/LOCAL-A', json={'status': 'resolved'}).json()
    assert item['activity'][-1]['member_name'] == 'Alex Rivera'
    assert item['resolution_events'][-1]['member_id'] == user


def test_oauth_captures_full_name(environment, monkeypatch):
    state = parse_qs(urlparse(salesforce.authorization_url()).query)['state'][0]
    def response(url, **kwargs):
        return {'access_token': 'token', 'instance_url': ORG, 'id': ORG + '/identity'} if url.endswith('/token') else {'user_id': 'user-a', 'display_name': 'Alex Rivera'}
    monkeypatch.setattr(salesforce, '_json_request', response)
    token = salesforce.complete_authorization('fake', state)
    assert salesforce._session(token).display_name == 'Alex Rivera'


def test_pagination_cannot_send_token_to_another_host(environment, monkeypatch):
    session(environment)
    monkeypatch.setattr(salesforce, '_json_request', lambda *a, **k: {'listviews': [], 'nextRecordsUrl': 'https://evil.example/page'})
    with pytest.raises(HTTPException) as error:
        salesforce.roster_support_cases(salesforce._session('session-a'))
    assert error.value.status_code == 502


@pytest.mark.parametrize("code", [401, 403])
def test_provider_auth_errors_are_explicit(monkeypatch, code):
    from urllib.error import HTTPError
    def fail(*args, **kwargs):
        raise HTTPError("https://example.my.salesforce.com", code, "private provider detail", {}, None)
    monkeypatch.setattr(salesforce, 'urlopen', fail)
    with pytest.raises(HTTPException) as error:
        salesforce._json_request('https://example.my.salesforce.com/resource', token='secret')
    assert error.value.status_code == code
    assert 'private provider detail' not in error.value.detail
    assert 'secret' not in error.value.detail
