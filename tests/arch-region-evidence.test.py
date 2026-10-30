import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'worker'))
from arch_region_evidence import summarize_side_logits,bilateral_regions
class ArchRegionEvidence(unittest.TestCase):
 def logits(self,g1,g2):
  return {'upper_left':[31.0,31.0-g1],'upper_right':[31.0,31.0-g2]}
 def test_actual_positives_only_support_not_verify(self):
  for a,b in ((.6155,.2993),(1.770,2.2684),(1.6489,3.0316)):
   with self.subTest(a=a):
    result=summarize_side_logits(self.logits(a,b))
    self.assertEqual(result['verdict'],'bilateral_arch_supported')
    self.assertNotEqual(result['verdict'],'verified')
 def test_real_and_hard_negative_pairs_do_not_support(self):
  for a,b in ((-.9542,-1.2875),(-.9542,-1.2909),(-1.6695,-1.684),
              (-1.5473,-2.7369),(-.2149,-1.9046),(1.,-.001)):
   with self.subTest(a=a):
    self.assertEqual(summarize_side_logits(self.logits(a,b))['verdict'],'unobservable')
 def test_missing_or_nonfinite_is_not_support(self):
  for x in ({},{'upper_left':[1,0]},self.logits(float('nan'),2),
            {'upper_left':[1,0],'upper_right':[None,0]}):
   self.assertEqual(summarize_side_logits(x)['verdict'],'unobservable')
 def test_same_predeclared_spatial_crop(self):
  self.assertEqual(bilateral_regions((1024,592)),
    {'upper_left':(0,0,369,385),'upper_right':(655,0,1024,385)})
  self.assertIsNone(bilateral_regions((100,80)))
if __name__=='__main__':unittest.main()
