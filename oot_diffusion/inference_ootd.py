import random
import sys
import time
from pathlib import Path

from huggingface_hub import snapshot_download
import torch
from diffusers import AutoencoderKL, UniPCMultistepScheduler
from transformers import (
    AutoProcessor,
    CLIPTextModel,
    CLIPTokenizer,
    CLIPVisionModelWithProjection,
)

from typing import Union

from . import pipelines_ootd

#! Necessary for OotdPipeline.from_pretrained
sys.modules["pipelines_ootd"] = pipelines_ootd

from .pipelines_ootd.pipeline_ootd import OotdPipeline
from .pipelines_ootd.unet_garm_2d_condition import UNetGarm2DConditionModel
from .pipelines_ootd.unet_vton_2d_condition import UNetVton2DConditionModel


class OOTDiffusion:
    def __init__(self, hg_root: str, model_type: str = "dc", cache_dir: str = None):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.hg_root = hg_root
        self.cache_dir = cache_dir

        if model_type not in ("hd", "dc"):
            raise ValueError(f"model_type must be 'hd' or 'dc', got {model_type!r}")

        self.model_type = model_type

        # hg_root = str(Path.cwd().resolve() / hg_root)
        VIT_PATH = "openai/clip-vit-large-patch14"
        VAE_PATH = f"{hg_root}/checkpoints/ootd"

        if not Path(VAE_PATH).exists():
            print("Downloading VAE model")
            snapshot_download(
                "levihsu/OOTDiffusion",
                cache_dir=cache_dir,
                local_dir=hg_root,
                allow_patterns=["**/ootd/**"],
            )

        if model_type == "hd":
            UNET_PATH = f"{hg_root}/checkpoints/ootd/ootd_hd/checkpoint-36000"
        else:
            UNET_PATH = f"{hg_root}/checkpoints/ootd/ootd_dc/checkpoint-36000"
        MODEL_PATH = f"{hg_root}/checkpoints/ootd"

        vae = AutoencoderKL.from_pretrained(
            VAE_PATH, subfolder="vae", torch_dtype=torch.float16, cache_dir=cache_dir
        )
        unet_garm = UNetGarm2DConditionModel.from_pretrained(
            UNET_PATH,
            subfolder="unet_garm",
            torch_dtype=torch.float16,
            use_safetensors=True,
        )
        unet_vton = UNetVton2DConditionModel.from_pretrained(
            UNET_PATH,
            subfolder="unet_vton",
            torch_dtype=torch.float16,
            use_safetensors=True,
        )
        self.pipe = OotdPipeline.from_pretrained(
            MODEL_PATH,
            unet_garm=unet_garm,
            unet_vton=unet_vton,
            vae=vae,
            torch_dtype=torch.float16,
            # variant="fp16",
            # use_safetensors=True,
            safety_checker=None,
            requires_safety_checker=False,
        ).to(self.device)

        self.pipe.scheduler = UniPCMultistepScheduler.from_config(
            self.pipe.scheduler.config
        )
        self.auto_processor = AutoProcessor.from_pretrained(
            VIT_PATH,
            cache_dir=cache_dir,
        )
        self.image_encoder = CLIPVisionModelWithProjection.from_pretrained(VIT_PATH).to(
            self.device,
        )
        self.tokenizer = CLIPTokenizer.from_pretrained(
            MODEL_PATH,
            subfolder="tokenizer",
        )
        self.text_encoder = CLIPTextModel.from_pretrained(
            MODEL_PATH,
            subfolder="text_encoder",
        ).to(self.device)

    def tokenize_captions(self, captions, max_length):
        inputs = self.tokenizer(
            captions,
            max_length=max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        return inputs.input_ids

    def __call__(
        self,
        category="upperbody",
        image_garm=None,
        image_vton=None,
        mask=None,
        image_ori=None,
        num_samples=1,
        num_steps=20,
        image_scale=1.0,
        seed=-1,
    ):
        if seed == -1:
            random.seed(time.time())
            seed = random.randint(0, 0xFFFFFFFFFFFFFFFF)
        print("Initial seed: " + str(seed))
        generator = torch.manual_seed(seed)

        with torch.no_grad():
            prompt_image = self.auto_processor(
                images=image_garm, return_tensors="pt"
            ).to(self.device)
            prompt_image = self.image_encoder(
                prompt_image.data["pixel_values"]
            ).image_embeds
            prompt_image = prompt_image.unsqueeze(1)
            if self.model_type == "hd":
                prompt_embeds = self.text_encoder(
                    self.tokenize_captions([""], 2).to(self.device)
                )[0]
                prompt_embeds[:, 1:] = prompt_image[:]
            elif self.model_type == "dc":
                prompt_embeds = self.text_encoder(
                    self.tokenize_captions([category], 3).to(self.device)
                )[0]
                prompt_embeds = torch.cat([prompt_embeds, prompt_image], dim=1)
            else:
                raise ValueError("model_type must be 'hd' or 'dc'!")

            images = self.pipe(
                prompt_embeds=prompt_embeds,
                image_garm=image_garm,
                image_vton=image_vton,
                mask=mask,
                image_ori=image_ori,
                num_inference_steps=num_steps,
                image_guidance_scale=image_scale,
                num_images_per_prompt=num_samples,
                generator=generator,
            ).images

        return images
