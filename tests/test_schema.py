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
        with patch('main.request',side_effect=fake),patch('main.hardware',return_value={}):asyncio.run(check())
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
