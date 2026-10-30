import unittest
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"worker"))
from wardrobe_contract import wants_unclothed, clothing_alignment, requested_outerwear_color

class WardrobeContractTest(unittest.TestCase):
 def test_worn_color_ignores_negated_historical_outfit(self):
  self.assertEqual(requested_outerwear_color(
   "fitted short navy-blue waist-length travel jacket, dark trousers, brown leather boots; no old green cloak"),"blue")
  self.assertEqual(requested_outerwear_color(
   "a green closed traveling cloak and brown boots"),"green")
  self.assertEqual(requested_outerwear_color(
   "a red fitted jacket, black trousers; no green cloak"),"red")
  self.assertEqual(requested_outerwear_color(
   "black trousers, a blue jacket; without any old green cloak"),"blue")
  self.assertIsNone(requested_outerwear_color(
   "old blue jacket discarded; no green cloak"))
  self.assertIsNone(requested_outerwear_color(
   "unclothed, green cloak held off body"))

 def test_compound_outfit_is_unclothed(self):
  self.assertTrue(wants_unclothed("fully undressed, green cloak and clothes gathered on her arm"))
  self.assertTrue(wants_unclothed("completely naked; cloak in hand"))
  self.assertFalse(wants_unclothed("green cloak and boots"))
  self.assertFalse(wants_unclothed("not nude, fully dressed"))
 def test_explicitly_dressed_caption_rejected(self):
  self.assertEqual(clothing_alignment("One woman wearing a green dress and boots."),"failed")
  self.assertEqual(clothing_alignment("An adult dressed in a cloak."),"failed")
 def test_verifiable_unclothed_caption_is_accepted(self):
  self.assertEqual(clothing_alignment("One adult with no clothes visible."),"passed")
  self.assertEqual(clothing_alignment("No garments worn; holding a cloak in her hand."),"passed")
 def test_ambiguous_caption_is_not_silently_passed(self):
  self.assertEqual(clothing_alignment("An adult character against a studio background."),"uncertain")

if __name__=="__main__":
 unittest.main()
