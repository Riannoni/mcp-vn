"""Zero-GPU adversarial SDXL face-chain tests; no private assets or model weights."""
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "worker"))
from identity_graph_contract import IdentityGraphBlocked, validate_sdxl_identity_graph

FACE = "a" * 64
FACE2 = "b" * 64
MASK = "c" * 64
MASK2 = "d" * 64
UP = "e" * 64
CKPT = "CyberRealisticPony_V18.0_F16.safetensors"

def node(kind, **inputs):
    return {"class_type": kind, "inputs": inputs}

def receipt(name, digest):
    return {"image": name, "source_sha256": digest, "upload_sha256": UP}

def base():
    return {"1": node("CheckpointLoaderSimple", ckpt_name=CKPT),
            "2": node("EmptyLatentImage", width=832, height=1216, batch_size=1),
            "5": node("KSampler", model=["1",0], latent_image=["2",0]),
            "6": node("VAEDecode", samples=["5",0], vae=["1",2]),
            "7": node("SaveImage", images=["6",0])}

def sprite():
    g = base()
    g.update({"15": node("CLIPVisionLoader",clip_name="CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors"),
              "16": node("IPAdapterModelLoader",ipadapter_file="ip-adapter-plus-face_sdxl_vit-h.safetensors"),
              "17": node("LoadImage",image="face0.png"),
              "18": node("IPAdapterAdvanced",model=["1",0],ipadapter=["16",0],image=["17",0],
                         clip_vision=["15",0],weight=.78,start_at=0.,end_at=.9,
                         weight_type="linear",combine_embeds="concat",embeds_scaling="V only")})
    g["5"]["inputs"]["model"]=["18",0]
    return g

def cg():
    g=base()
    g.update({"60":node("CLIPVisionLoader",clip_name="CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors"),
              "61":node("IPAdapterModelLoader",ipadapter_file="ip-adapter-plus-face_sdxl_vit-h.safetensors")})
    for i, image in enumerate(("face0.png","face1.png")):
        im, mask, app=map(str,(62+3*i,63+3*i,64+3*i))
        g[im]=node("LoadImage",image=image)
        g[mask]=node("LoadImage",image=f"mask{i}.png")
        g[app]=node("IPAdapterAdvanced",model=["1",0] if i==0 else ["64",0],
                    ipadapter=["61",0],image=[im,0],clip_vision=["60",0],
                    attn_mask=[mask,1],weight=.74,start_at=0.,end_at=.95,
                    weight_type="linear",combine_embeds="concat",embeds_scaling="V only")
    g["5"]["inputs"]["model"]=["67",0]
    return g

ONE={"status":"SOURCE_INTENT_CONSISTENT_NOT_G2","actors":[
    {"name":"Actor_A","face_sha256":FACE,"face_asset":"f0.png","outfit":"closed navy jacket"}]}
TWO={"status":"SOURCE_INTENT_CONSISTENT_NOT_G2","actors":ONE["actors"] + [
    {"name":"Actor_B","face_sha256":FACE2,"face_asset":"f1.png","outfit":"closed brown coat"}]}
SJOB={"kind":"sprite","spec":{"character":"Actor_A","face_asset":"f0.png",
                             "variant":{"outfit":"closed navy jacket"}}}
CJOB={"kind":"scene","spec":{"composition":"neural_story","characters":[
    {"name":"Actor_A","anchor_face_asset":"f0.png","outfit":"closed navy jacket","actor_region":[.1,.1,.3,.7]},
    {"name":"Actor_B","anchor_face_asset":"f1.png","outfit":"closed brown coat","actor_region":[.6,.1,.3,.7]}]}}
SU={"Actor_A":receipt("face0.png",FACE)}
CU={**SU,"Actor_B":receipt("face1.png",FACE2)}
CM={"Actor_A":{**receipt("mask0.png",MASK),"actor_region":[.1,.1,.3,.7]},
    "Actor_B":{**receipt("mask1.png",MASK2),"actor_region":[.6,.1,.3,.7]}}

def check(job,graph,intent,faces,masks=None,body=None):
    return validate_sdxl_identity_graph(job,graph,intent,checkpoint=CKPT,
                                         face_uploads=faces,mask_uploads=masks,body_source=body)

class IdentityGraphContractTests(unittest.TestCase):
    def test_valid_fresh_sprite_only_claims_wiring(self):
        r=check(SJOB,sprite(),ONE,SU)
        self.assertEqual(r["status"],"GRAPH_IDENTITY_WIRED_NOT_G2")
        self.assertIs(r["pixel_reviewed"],False)

    def test_valid_two_principal_cg_only_claims_wiring(self):
        self.assertEqual(check(CJOB,cg(),TWO,CU,CM)["actor_count"],2)

    def test_final_saved_png_must_come_from_canonical_sampler(self):
        g=sprite();g["7"]["inputs"]["images"]=["77",0]
        g["77"]=node("VAEDecode", samples=["5",0], vae=["1",2])
        with self.assertRaisesRegex(IdentityGraphBlocked, "output|SaveImage|decoder"):
            check(SJOB,g,ONE,SU)
        g=sprite();g["6"]["inputs"]["samples"]=["99",0]
        g["99"]=node("KSampler", model=["1",0], latent_image=["2",0])
        with self.assertRaisesRegex(IdentityGraphBlocked, "output|sampler|decoder"):
            check(SJOB,g,ONE,SU)

    def test_second_output_or_sampler_cannot_escape_face_chain(self):
        g=sprite();g["89"]=node("SaveImage", images=["6",0])
        with self.assertRaisesRegex(IdentityGraphBlocked, "output|SaveImage"):
            check(SJOB,g,ONE,SU)
        g=sprite();g["99"]=node("KSampler", model=["1",0], latent_image=["2",0])
        with self.assertRaisesRegex(IdentityGraphBlocked, "sampler"):
            check(SJOB,g,ONE,SU)

    def test_exact_review_counterexample_sprite_and_two_actor_cg(self):
        # Independent Integration red-case: a valid protected sampler exists,
        # but an unprotected sampler feeds the actual saved bytes.
        for kind, job, graph, intent, faces, masks in (
            ("sprite", SJOB, sprite(), ONE, SU, None),
            ("cg_2", CJOB, cg(), TWO, CU, CM),
        ):
            with self.subTest(kind=kind):
                graph["99"]=node("KSampler",model=["1",0],latent_image=["2",0])
                graph["100"]=node("VAEDecode",samples=["99",0],vae=["1",2])
                graph["7"]["inputs"]["images"]=["100",0]
                with self.assertRaisesRegex(IdentityGraphBlocked,"sampler|output"):
                    check(job,graph,intent,faces,masks)

    def test_ipadapter_embedding_semantics_are_frozen(self):
        for field,value in (("weight_type","style transfer"),
                            ("combine_embeds","average"),
                            ("embeds_scaling","K+V")):
            g=sprite();g["18"]["inputs"][field]=value
            with self.subTest(field=field), self.assertRaisesRegex(
                IdentityGraphBlocked, "IPAdapter|embedding"
            ):
                check(SJOB,g,ONE,SU)

    def test_optional_sprite_mask_cannot_zero_out_face_conditioning(self):
        graph = sprite()
        graph["90"] = node("SolidMask", value=0, width=832, height=1216)
        graph["18"]["inputs"]["attn_mask"] = ["90", 0]
        with self.assertRaisesRegex(IdentityGraphBlocked, "IPAdapter.*(optional|mask|input)"):
            check(SJOB, graph, ONE, SU)

    def test_optional_negative_image_cannot_override_canonical_face(self):
        for job, graph, intent, faces, masks, adapter_id in (
            (SJOB, sprite(), ONE, SU, None, "18"),
            (CJOB, cg(), TWO, CU, CM, "64"),
        ):
            with self.subTest(kind=job["kind"]):
                graph["91"] = node("LoadImage", image="other_face.png")
                graph[adapter_id]["inputs"]["image_negative"] = ["91", 0]
                with self.assertRaisesRegex(IdentityGraphBlocked, "IPAdapter.*(optional|negative|input)"):
                    check(job, graph, intent, faces, masks)

    def test_current_worker_silent_face_fallback_cannot_pass(self):
        g=sprite();g["5"]["inputs"]["model"]=["1",0]
        with self.assertRaisesRegex(IdentityGraphBlocked,"bypasses"):
            check(SJOB,g,ONE,SU)

    def test_removed_face_nodes_cannot_pass(self):
        g=sprite();del g["18"]
        with self.assertRaises(IdentityGraphBlocked):check(SJOB,g,ONE,SU)

    def test_corrupted_face_upload_original_digest(self):
        f=copy.deepcopy(SU);f["Actor_A"]["source_sha256"]=FACE2
        with self.assertRaisesRegex(IdentityGraphBlocked,"source SHA"):
            check(SJOB,sprite(),ONE,f)

    def test_swapped_face_uploads_per_actor(self):
        f=copy.deepcopy(CU);f["Actor_A"],f["Actor_B"]=f["Actor_B"],f["Actor_A"]
        with self.assertRaises(IdentityGraphBlocked):check(CJOB,cg(),TWO,f,CM)

    def test_swapped_face_graph_images(self):
        g=cg();g["62"]["inputs"]["image"]="face1.png"
        with self.assertRaisesRegex(IdentityGraphBlocked,"swapped"):
            check(CJOB,g,TWO,CU,CM)

    def test_swapped_or_disconnected_attention_mask(self):
        g=cg();g["64"]["inputs"]["attn_mask"]=["66",1]
        with self.assertRaisesRegex(IdentityGraphBlocked,"region"):
            check(CJOB,g,TWO,CU,CM)
        g=cg();g["63"]["inputs"]["image"]="mask1.png"
        with self.assertRaisesRegex(IdentityGraphBlocked,"region"):
            check(CJOB,g,TWO,CU,CM)

    def test_missing_region_receipt(self):
        with self.assertRaisesRegex(IdentityGraphBlocked,"region"):
            check(CJOB,cg(),TWO,CU,{})

    def test_adapter_bypassed_after_first_actor(self):
        g=cg();g["5"]["inputs"]["model"]=["64",0]
        with self.assertRaisesRegex(IdentityGraphBlocked,"bypasses"):
            check(CJOB,g,TWO,CU,CM)

    def test_rewired_actor_adapter_chain(self):
        g=cg();g["67"]["inputs"]["model"]=["1",0]
        with self.assertRaisesRegex(IdentityGraphBlocked,"disconnected"):
            check(CJOB,g,TWO,CU,CM)

    def test_wrong_backend_or_adapter_model(self):
        g=sprite();g["1"]["class_type"]="UNETLoader"
        with self.assertRaisesRegex(IdentityGraphBlocked,"CheckpointLoaderSimple"):
            check(SJOB,g,ONE,SU)
        g=sprite();g["16"]["inputs"]["ipadapter_file"]="ip-adapter_sd15.safetensors"
        with self.assertRaisesRegex(IdentityGraphBlocked,"Unsupported"):
            check(SJOB,g,ONE,SU)

    def test_disabled_face_weight(self):
        g=sprite();g["18"]["inputs"]["weight"]=0.
        with self.assertRaisesRegex(IdentityGraphBlocked,"ineffective"):
            check(SJOB,g,ONE,SU)
        g=sprite();g["18"]["inputs"]["end_at"]=0.
        with self.assertRaisesRegex(IdentityGraphBlocked,"ineffective"):
            check(SJOB,g,ONE,SU)

    def test_unattested_old_body_seed_must_be_blocked(self):
        g=sprite();g["10"]=node("LoadImage",image="old_body.png")
        g["11"]=node("VAEEncode",pixels=["10",0],vae=["1",2])
        g["5"]["inputs"]["latent_image"]=["11",0]
        with self.assertRaisesRegex(IdentityGraphBlocked,"Unattested"):
            check(SJOB,g,ONE,SU)
        with self.assertRaisesRegex(IdentityGraphBlocked,"stale"):
            check(SJOB,g,ONE,SU,body={**receipt("old_body.png",UP),"outfit":"old green cloak"})

    def test_attested_current_outfit_body_and_upload_must_match(self):
        g=sprite();g["10"]=node("LoadImage",image="current_body.png")
        g["11"]=node("VAEEncode",pixels=["10",0],vae=["1",2])
        g["5"]["inputs"]["latent_image"]=["11",0]
        body={**receipt("current_body.png",UP),"outfit":"closed navy jacket"}
        self.assertEqual(check(SJOB,g,ONE,SU,body=body)["status"],"GRAPH_IDENTITY_WIRED_NOT_G2")
        g["10"]["inputs"]["image"]="old_body.png"
        with self.assertRaisesRegex(IdentityGraphBlocked,"swapped"):
            check(SJOB,g,ONE,SU,body=body)

    def test_unexpected_extra_adapter_is_not_approved(self):
        g=sprite();g["99"]=node("IPAdapterAdvanced",model=["1",0])
        with self.assertRaisesRegex(IdentityGraphBlocked,"Extra"):
            check(SJOB,g,ONE,SU)

    def test_stale_intent_and_wardrobe_change_must_not_use_old_receipt(self):
        j=copy.deepcopy(SJOB);j["spec"]["variant"]["outfit"]="buttoned red uniform"
        with self.assertRaisesRegex(IdentityGraphBlocked,"Stale"):
            check(j,sprite(),ONE,SU)
        j=copy.deepcopy(CJOB);j["spec"]["characters"][1]["anchor_face_asset"]="new_face.png"
        with self.assertRaisesRegex(IdentityGraphBlocked,"Stale"):
            check(j,cg(),TWO,CU,CM)

    def test_mask_receipt_must_match_source_actor_region(self):
        masks=copy.deepcopy(CM);masks["Actor_A"]["actor_region"]=[.6,.1,.3,.7]
        with self.assertRaisesRegex(IdentityGraphBlocked,"source-bound"):
            check(CJOB,cg(),TWO,CU,masks)

    def test_malformed_job_fails_closed(self):
        with self.assertRaisesRegex(IdentityGraphBlocked,"spec missing"):
            check({"kind":"sprite","spec":"oops"},sprite(),ONE,SU)

    def test_cross_family_model_name_must_not_be_caller_selected(self):
        # Adversarial model swap: a matching caller-provided name cannot prove
        # the installed checkpoint is the approved Pony/SDXL family.
        for candidate in ("Z-Image-Turbo.safetensors", "unknown_sdxl.safetensors"):
            with self.subTest(checkpoint=candidate):
                g = sprite()
                g["1"]["inputs"]["ckpt_name"] = candidate
                with self.assertRaisesRegex(IdentityGraphBlocked, "Pony|checkpoint|family"):
                    validate_sdxl_identity_graph(
                        SJOB, g, ONE, checkpoint=candidate, face_uploads=SU
                    )

    def test_wrong_checkpoint_not_allowed(self):
        g=sprite();g["1"]["inputs"]["ckpt_name"]="wrong_family.safetensors"
        with self.assertRaisesRegex(IdentityGraphBlocked,"Checkpoint"):
            check(SJOB,g,ONE,SU)

if __name__=="__main__":
    unittest.main()
