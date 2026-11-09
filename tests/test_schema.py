import json, unittest
from pathlib import Path
from main import definitions,validate,MAINTENANCE,Plugin
import asyncio
from unittest.mock import patch
schema=json.loads(Path(__file__).parent.joinpath('fixtures/schema.json').read_text(encoding='utf-8'))
defs=definitions(schema)
class Tests(unittest.TestCase):
    def test_every_control_definition_validates(self):
        tested=0
        for path,node in defs.items():
            if path in MAINTENANCE:continue
            kind=node['type']
            if kind in ('bool','action'):value=False
            elif kind=='int':value=node['min']
            elif kind=='multiple':value=next(iter(node['options']))
            elif kind=='discrete':value=node['options'][0]
            else:continue
            with self.subTest(path=path):validate(schema,[{'path':path,'value':value}])
            tested+=1
        self.assertGreater(tested,90)
        print('Validated all',tested,'control paths across all mode branches')
    def test_rejects_invalid_values_and_paths(self):
        for path,value in [('tdp.asus.tdp_v2.custom.tdp',999),('tdp.asus.tdp_v2.custom.tdp',True),('tdp.asus.tdp_v2.mode','invalid'),('fake.key',1),('hhd.settings.version','x'),('tdp.asus.tdp_v2.custom.boost','false')]:
            with self.subTest(path=path),self.assertRaises(ValueError):validate(schema,[{'path':path,'value':value}])
    def test_update_is_blocked(self):
        for path in MAINTENANCE:
            with self.assertRaises(ValueError):validate(schema,[{'path':path,'value':True}])
    def test_advanced_controls_not_omitted(self):
        self.assertIn('controllers.rog_ally.rgb_boot',defs)
        self.assertIn('controllers.rog_ally.rgb_charging',defs)
        self.assertIn('tdp.amd_energy.mode.manual.cpu_boost',defs)
    def test_actual_decky_legacy_class_calling_convention(self):
        state={'version':'test','tdp':{'asus':{'tdp_v2':{'custom':{'tdp':14}}}}}
        def fake(method,endpoint,data=None):
            return {'settings':schema,'state':state,'sections':{'tdp':'TDP'}}[endpoint]
        async def check():
            await Plugin._main(Plugin)
            result=await Plugin.snapshot(Plugin)
            self.assertTrue(result['ok'],result)
            result=await Plugin.apply(Plugin,[{'path':'tdp.asus.tdp_v2.custom.tdp','value':14}])
            self.assertTrue(result['ok'],result)
        state['tdp']['asus']['tdp_v2']['mode']='custom'
        with patch('main.request',side_effect=fake),patch('main.hardware',return_value={'ppt_pl1_spl':'14','ppt_pl2_sppt':'14','ppt_fppt':'14'}):asyncio.run(check())

    def test_profile_saves_more_than_64_settings_without_actions(self):
        state=json.loads(Path(__file__).parent.joinpath('fixtures/state.json').read_text())
        saved=[]
        def fake(method,endpoint,data=None):
            if endpoint=='settings':return schema
            saved.append(data);return None
        async def check():
            result=await Plugin().profiles('set','Regression Profile',state)
            self.assertTrue(result['ok'],result)
        with patch('main.request',side_effect=fake):asyncio.run(check())
        flattened={p for p in defs if __import__('main').get_path(saved[0],p) is not None}
        self.assertGreater(len(flattened),64)
        self.assertTrue(all(defs[p]['type']!='action' for p in flattened))

    def test_tdp_edit_activates_custom_and_checks_hardware(self):
        from main import get_path
        state={'version':'fixture','tdp':{'asus':{'tdp_v2':{'mode':'performance','custom':{'tdp':30,'boost':False}}}}}
        writes=[]
        def fake(method,endpoint,data=None):
            if endpoint=='settings':return schema
            if endpoint=='sections':return {}
            if method=='POST':
                writes.append(data)
                state['tdp']['asus']['tdp_v2'].update(data['tdp']['asus']['tdp_v2'])
            return state
        p=Plugin()
        with patch('main.request',side_effect=fake),patch('main.hardware',return_value={'ppt_pl1_spl':'15','ppt_pl2_sppt':'15','ppt_fppt':'15'}):
            result=p._apply([{'path':'tdp.asus.tdp_v2.custom.tdp','value':15}])
        self.assertEqual(get_path(writes[0],'tdp.asus.tdp_v2.mode'),'custom')
        self.assertTrue(result['ok'])
        with patch('main.request',side_effect=fake),patch('main.hardware',return_value={'ppt_pl1_spl':'30'}),patch('main.time.sleep'):
            with self.assertRaisesRegex(ValueError,'硬件'):
                p._apply([{'path':'tdp.asus.tdp_v2.custom.tdp','value':15}])

    def test_profile_apply_uses_saved_values_despite_stale_post_response(self):
        from copy import deepcopy
        from main import get_path
        desired=json.loads(Path(__file__).parent.joinpath('fixtures/state.json').read_text())
        desired['tdp']['asus']['tdp_v2'].update(mode='custom',custom={'tdp':15,'boost':False})
        current=deepcopy(desired)
        current['tdp']['asus']['tdp_v2']['custom']['tdp']=14
        def merge(target,source):
            for key,value in source.items():
                if isinstance(value,dict):merge(target.setdefault(key,{}),value)
                else:target[key]=value
        def fake(method,endpoint,data=None):
            if endpoint=='settings':return schema
            if endpoint=='sections':return {}
            if endpoint.startswith('profile/get?'):return desired
            self.assertFalse(endpoint.startswith('profile/apply'), 'Unverified shared-condition endpoint used')
            if method=='POST':
                stale=deepcopy(current);merge(current,data);return stale
            return current
        async def check():
            result=await Plugin().profiles('apply','Regression Profile',confirmed=True)
            self.assertTrue(result['ok'],result)
            self.assertEqual(get_path(result['result'],'tdp.asus.tdp_v2.custom.tdp'),15)
        with patch('main.request',side_effect=fake),patch('main.hardware',return_value={'ppt_pl1_spl':'15','ppt_pl2_sppt':'15','ppt_fppt':'15'}),patch('main.time.sleep'):
            asyncio.run(check())
    def test_snapshot_cache_preserves_full_schema_on_version_change(self):
        state={'version':'fixture-version'}
        def fake(method,endpoint,data=None):
            return {'settings':schema,'state':state,'sections':{'tdp':'TDP'}}[endpoint]
        async def check():
            await Plugin._main(Plugin)
            full=await Plugin.snapshot(Plugin)
            self.assertIn('settings',full)
            cached=await Plugin.snapshot(Plugin,known_version='fixture-version')
            self.assertTrue(cached['ok'])
            self.assertNotIn('settings',cached)
            self.assertNotIn('sections',cached)
            self.assertEqual(cached['state'],state)
            changed=await Plugin.snapshot(Plugin,known_version='older-version')
            self.assertIn('settings',changed)
            self.assertIn('sections',changed)
        with patch('main.request',side_effect=fake),patch('main.hardware',return_value={}):asyncio.run(check())
if __name__=='__main__':unittest.main(verbosity=2)
