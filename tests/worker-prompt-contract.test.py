"""Regression coverage for storytelling-to-Comfy generation boundaries.

Stdlib-only: extract prompt_builder rather than importing GPU runtime modules.
"""
import ast
import re
import unittest
from pathlib import Path

WORKER=Path(__file__).resolve().parents[1]/"worker"/"worker.py"


class WorkerPromptContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source=WORKER.read_text()
        tree=ast.parse(source)
        node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and
                  n.name=="prompt_builder")
        module=ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[]))
        namespace={
            "re":re,
            "background_context":lambda _:( "overcast", ""),
            "appearance_tags":lambda _: "adult with dark hair",
            "neural_scene_guards":lambda *_:("SOLO SUBJECT. ","duplicate person, ","v1"),
            "scene_constraints":lambda *_:("SCENE_CONTRACT. ","worn clothing")
        }
        exec(compile(module,str(WORKER),"exec"),namespace)
        cls.prompt_builder=staticmethod(namespace["prompt_builder"])
        cls.source=source

    def test_forest_scene_is_never_forced_into_market_or_unclothed(self):
        j={"kind":"scene","style":"semireal","prompt":
           "One adult traveler standing in a forest clearing, front view.",
           "attempts":1,"spec":{"location":"Pine forest","composition":"neural_story",
           "narrator_prompt":True,"environment":{"id":"outdoor_forest",
           "positive":["pine woods"],"negative":["city buildings"]},
           "characters":[{"name":"Ada","appearance":"adult with dark hair"}]}}
        positive,negative=self.prompt_builder(j,None)
        self.assertIn("forest clearing",positive)
        self.assertNotIn("Market square with brick buildings",positive)
        self.assertNotIn("MUST BE FULLY NUDE",positive)
        self.assertNotIn("MUST BE FROM BEHIND",positive)
        self.assertNotIn("rating_explicit",positive)
        self.assertIn("duplicate person",negative)

    def test_keyword_wall_does_not_force_unrelated_camera_pose(self):
        j={"kind":"scene","style":"semireal","prompt":
           "One adult in front of a wall facing the viewer.",
           "attempts":1,"spec":{"location":"Hallway",
           "environment":{"id":"indoor_room","positive":["hallway"],"negative":[]},
           "characters":[{"name":"Ada","appearance":"adult"}]}}
        positive,_=self.prompt_builder(j,None)
        self.assertIn("facing the viewer",positive)
        self.assertNotIn("MUST BE FROM BEHIND",positive)
        self.assertNotIn("MUST BE FULLY NUDE",positive)
        self.assertNotIn("Market square with brick buildings",positive)

    def test_no_fallback_forces_failed_qa_to_pass(self):
        self.assertNotIn("QUALITY_ACCEPTED_FALLBACK",self.source)
        self.assertNotIn('report["passed"]=True',self.source)
        self.assertIn('print("QUALITY_REJECTED"',self.source)


if __name__=="__main__":
    unittest.main()
