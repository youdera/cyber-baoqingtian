"""Regression cases for one official URL discovered in more than one directory."""
import copy
import hashlib
import tempfile
import unittest
from unittest.mock import patch

from notice_app import create_app
from wuzhong.notices import SOURCES, NoticeStore, relevance, source_views, validate_filters


SOURCE_A = next(s for s in SOURCES if s['id'] == 'shanxi_sydw')
SOURCE_B = next(s for s in SOURCES if s['id'] == 'shanxi_sydw_jobs')
URL = 'https://rst.shanxi.gov.cn/rsks/sydwks/synthetic-shared-notice.html'
NOTICE_ID = hashlib.sha256(URL.encode()).hexdigest()
T1, T2, T3, T4 = [f'2026-09-12T0{i}:00:00+00:00' for i in range(1, 5)]


def notice(source=SOURCE_A, **changes):
    item = dict(id=NOTICE_ID, url=URL, title='2026年模拟事业单位拟聘用公示',
                source_id=source['id'], source=source['name'], owner=source['owner'],
                published='2026-05-01', exam_year=2026, kind='事业单位',
                region='山西', stage='录聘公示')
    item.update(changes)
    return item


def filters(source_id=''):
    return dict(month_from='2026-01', month_to='2026-12', year_from=2026,
                area_scope='province', region='山西', kind='事业单位',
                notice_scope='public', source_id=source_id)


def observe(store, item, timestamp):
    with patch('wuzhong.notices.now', return_value=timestamp):
        return store.record(item)


def watch(store, id, source_id=''):
    store.put('saved', dict(id=id, enabled=True, notify_enabled=True,
                            filters=validate_filters(filters(source_id))))


def views(store):
    return {view['source_id']: view for view in source_views(store.all('entries')[0])}


class SourceRecordTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.app = create_app(self.folder.name, schedule=False)
        self.store = self.app.extensions['store']
        self.client = self.app.test_client()
        state = self.client.get('/api/notices/state').json
        self.headers = {'X-Local-Token': state['token']}

    def query(self, source_id=''):
        response = self.client.post('/api/notices/query', headers=self.headers,
                                    json=filters(source_id))
        self.assertEqual(response.status_code, 200, response.json)
        return response.json['records']

    def test_same_url_retains_each_directorys_metadata_without_overwriting_primary(self):
        a = notice(published='2026-05-01')
        b = notice(SOURCE_B, published='2026-05-03')
        observe(self.store, a, T1)
        observe(self.store, b, T2)
        entries = self.store.all('entries')
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['id'], NOTICE_ID)
        self.assertEqual(entries[0]['source_id'], SOURCE_A['id'])
        self.assertEqual(entries[0]['published'], '2026-05-01')
        per_source = views(self.store)
        self.assertEqual(set(per_source), {SOURCE_A['id'], SOURCE_B['id']})
        for original in (a, b):
            for field in ('id', 'url', 'title', 'source_id', 'source', 'owner', 'published'):
                self.assertEqual(per_source[original['source_id']][field], original[field])

    def test_alternating_unchanged_observations_do_not_update_or_realert(self):
        watch(self.store, 'broad')
        watch(self.store, 'only_b', SOURCE_B['id'])
        a, b = notice(), notice(SOURCE_B)
        observe(self.store, a, T1)
        observe(self.store, b, T2)
        alerts_before = copy.deepcopy(self.store.all('alerts'))
        revisions_before = {sid: view.get('revision') for sid, view in views(self.store).items()}
        for index in range(3):
            self.assertEqual(observe(self.store, a, T3), (0, 0), f'A pass {index}')
            self.assertEqual(observe(self.store, b, T4), (0, 0), f'B pass {index}')
        self.assertEqual(self.store.all('alerts'), alerts_before)
        self.assertEqual({sid: view.get('revision') for sid, view in views(self.store).items()},
                         revisions_before)
        self.assertEqual(len(self.store.all('entries')), 1)

    def test_shared_content_deduplicates_broad_watch_but_not_specific_b_watch(self):
        watch(self.store, 'broad')
        watch(self.store, 'only_b', SOURCE_B['id'])
        observe(self.store, notice(), T1)
        self.assertEqual([a['saved_id'] for a in self.store.all('alerts')], ['broad'])
        observe(self.store, notice(SOURCE_B), T2)
        alerts = self.store.all('alerts')
        self.assertEqual(sorted(a['saved_id'] for a in alerts), ['broad', 'only_b'])
        self.assertEqual(next(a for a in alerts if a['saved_id'] == 'only_b')['source'], SOURCE_B['name'])

        changed_title = '2026年模拟事业单位拟聘用公示（更正）'
        observe(self.store, notice(title=changed_title), T3)
        observe(self.store, notice(SOURCE_B, title=changed_title), T4)
        alerts = self.store.all('alerts')
        self.assertEqual(sum(a['saved_id'] == 'broad' for a in alerts), 2)
        self.assertEqual(sum(a['saved_id'] == 'only_b' for a in alerts), 2)

    def test_matched_directory_is_selected_ahead_of_review_directory(self):
        observe(self.store, notice(published=None), T1)
        observe(self.store, notice(SOURCE_B), T2)
        per_source = views(self.store)
        f = validate_filters(filters())
        self.assertEqual(relevance(per_source[SOURCE_A['id']], f), 'review')
        self.assertEqual(relevance(per_source[SOURCE_B['id']], f), 'matched')
        self.assertEqual(relevance(self.store.all('entries')[0], f), 'matched')
        records = self.query()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['match_status'], 'matched')
        self.assertEqual(records[0]['source_id'], SOURCE_B['id'])
        self.assertEqual(records[0]['published'], '2026-05-01')
        self.assertEqual({s['id'] for s in records[0]['matching_sources']},
                         {SOURCE_A['id'], SOURCE_B['id']})

    def test_b_query_keeps_its_own_dates_and_change_state_when_a_changes(self):
        a = notice(published='2026-05-01')
        b = notice(SOURCE_B, published='2026-05-03')
        observe(self.store, a, T1)
        observe(self.store, b, T2)
        b_changed = dict(b, title='2026年模拟事业单位拟聘用公示（更正）')
        observe(self.store, b_changed, T3)
        before = self.query(SOURCE_B['id'])[0]
        self.assertEqual(before['changed_at'], T3)
        self.assertEqual(before['first_seen'], T2)
        self.assertEqual(before['checked_at'], T3)

        observe(self.store, dict(a, title='2026年模拟事业单位拟聘用公示（补充公告）',
                                 published='2026-05-02'), T4)
        after = self.query(SOURCE_B['id'])[0]
        for field in ('source_id', 'source', 'owner', 'title', 'published',
                      'first_seen', 'checked_at', 'changed_at', 'revision'):
            self.assertEqual(after[field], before[field], field)
        self.assertEqual(after['published'], '2026-05-03')
        self.assertEqual([s['id'] for s in after['matching_sources']], [SOURCE_B['id']])
        self.assertEqual(self.query(SOURCE_A['id'])[0]['published'], '2026-05-02')

    def test_legacy_single_source_record_is_readable_without_migration(self):
        legacy = dict(notice(), first_seen=T1, checked_at=T2, changed_at=None)
        self.store.put('entries', legacy)
        reopened = NoticeStore(self.folder.name)
        before = copy.deepcopy(reopened.all('entries'))
        self.assertEqual(source_views(before[0]), [legacy])
        records = self.query(SOURCE_A['id'])
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['id'], NOTICE_ID)
        self.assertEqual(records[0]['first_seen'], T1)
        self.assertEqual([s['id'] for s in records[0]['matching_sources']], [SOURCE_A['id']])
        self.assertEqual(self.query(SOURCE_B['id']), [])
        self.assertEqual(reopened.all('entries'), before)
        self.assertNotIn('source_records', reopened.all('entries')[0])

    def test_legacy_record_gains_second_source_on_observation_without_changing_id(self):
        legacy = dict(notice(), first_seen=T1, checked_at=T1, changed_at=None)
        self.store.put('entries', legacy)
        observe(self.store, notice(SOURCE_B, published='2026-05-03'), T2)
        entries = self.store.all('entries')
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['id'], NOTICE_ID)
        per_source = views(self.store)
        self.assertEqual(per_source[SOURCE_A['id']]['first_seen'], T1)
        self.assertEqual(per_source[SOURCE_A['id']]['checked_at'], T1)
        self.assertEqual(per_source[SOURCE_A['id']]['published'], '2026-05-01')
        self.assertEqual(per_source[SOURCE_B['id']]['first_seen'], T2)
        self.assertEqual(per_source[SOURCE_B['id']]['published'], '2026-05-03')
        self.assertEqual(self.query(SOURCE_B['id'])[0]['id'], NOTICE_ID)


if __name__ == '__main__': unittest.main()
