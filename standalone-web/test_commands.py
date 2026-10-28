import copy
import json
import unittest
from unittest.mock import patch
import vn_web as vn

GAME='11111111-1111-4111-8111-111111111111'
CATALOG={'connected':True,'models':[{'id':'local-test'}]}
PACKET={'pending_narration':True,'pending_action':{'id':'action-1'},
        'command':{'name':'improvise','instruction':'Разрешено описать действия героя.'}}

class CommandsTests(unittest.TestCase):
 def test_ooc_and_recap_never_write_story(self):
  for text in ['/ooc где мы?', '/recap']:
   calls=[]
   def home(path,payload=None,timeout=35):
    calls.append((path,payload));return {'packet':{'story':{'title':'Тест'},'recent_dialogue':[]}}
   with patch.object(vn,'models',return_value=CATALOG),patch.object(vn,'home',side_effect=home),patch.object(vn,'proxy',return_value={'choices':[{'message':{'content':'Краткий ответ.'}}]}):
    result=vn.command(GAME,'local-test',text,1)
   self.assertEqual(result['text'],'Краткий ответ.')
   self.assertEqual(calls,[('context/'+GAME,None)])

 def test_unknown_and_empty_commands_fail_before_any_request(self):
  for text in ['/bad', '/skip', '/ooc', '/undo extra', '/recap extra']:
   with patch.object(vn,'home') as home,patch.object(vn,'proxy') as proxy:
    with self.assertRaises(vn.VNError):vn.command(GAME,'local-test',text,1)
    home.assert_not_called();proxy.assert_not_called()

 def test_undo_and_video_require_explicit_confirmation_without_calling_model(self):
  for text in ['/undo','/video']:
   with patch.object(vn,'home') as home,patch.object(vn,'proxy') as proxy:
    with self.assertRaises(vn.VNError):vn.command(GAME,'local-test',text,1)
    home.assert_not_called();proxy.assert_not_called()

 def test_resume_preserves_command_and_does_not_submit_again(self):
  calls=[];requests=[]
  def home(path,payload=None,timeout=35):
   calls.append(path)
   if path.startswith('packet/'):return {'packet':copy.deepcopy(PACKET)}
   if path=='commit':return {'game':{'id':GAME}}
   return {'visual':{}}
  def proxy(path,payload=None,timeout=35):
   requests.append(payload)
   return {'choices':[{'message':{'content':'{"messages":[{"text":"Продолжение."}]}'}}]}
  with patch.object(vn,'models',return_value=CATALOG),patch.object(vn,'home',side_effect=home),patch.object(vn,'proxy',side_effect=proxy):
   vn.turn(GAME,'local-test')
  self.assertNotIn('submit',calls)
  self.assertIn('Разрешено описать действия героя.',requests[0]['messages'][0]['content'])

 def test_narration_preserves_flags_and_only_explicit_appearance_fields(self):
  answer=vn.parse_answer(json.dumps({'messages':[{'text':'Мира снимает плащ.'}],
   'scene':{'sprites':[{'name':'Мира','outfit':'undressed'}]},
   'flags':{'mira_fully_undressed':True,'mira_dressed_again':False,
            'bad flag!':True,'not_a_scalar':{'x':1}}},ensure_ascii=False))
  self.assertEqual(answer['flags'],{'mira_fully_undressed':True,'mira_dressed_again':False})
  self.assertEqual(answer['scene']['sprites'],[{'name':'Мира','outfit':'undressed'}])
  self.assertEqual(vn.parse_answer('{"messages":[{"text":"Тест"}],"scene":{"sprites":[]}}')['scene']['sprites'],[])

 def test_narrator_art_prompts_survive_parse_with_bounds(self):
  payload={'messages':[{'text':'Мира остановилась у стены.'}],
   'scene':{'visual_mode':'cg','image_prompts':{
    'cg':'Exact cinematic composition: one character next to a stone wall.',
    'background':'Empty market square in early evening.',
    'sprites':{'Мира':'Single character, correct current pose and clothing.'}}}}
  response=vn.parse_answer(json.dumps(payload,ensure_ascii=False))
  self.assertEqual(response['scene']['image_prompts'],payload['scene']['image_prompts'])
  self.assertEqual(response['scene']['visual_mode'],'cg')

 def test_video_assets_are_same_origin_and_invalid_names_are_rejected(self):
  self.assertEqual(vn.asset_url('https://xavoks.jo3.org/vn/assets/'+GAME+'.mp4?sig=x'),'/api/vn/assets/'+GAME+'.mp4')
  with self.assertRaises(vn.VNError):vn.asset_bytes('../secret.mp4')

if __name__=='__main__':unittest.main()
