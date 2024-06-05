# coding=utf-8
# Copyright 2022 The HuggingFace Team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import inspect
import unittest


from mindnlp.transformers import GitConfig, GitVisionConfig
from mindnlp.transformers.models.auto import get_values
from mindnlp.utils.testing_utils import  slow, require_mindspore ,is_mindspore_available

from ...generation.test_utils import GenerationTesterMixin
from ...test_configuration_common import ConfigTester
from ...test_modeling_common import ModelTesterMixin, floats_tensor, ids_tensor, random_attention_mask


if is_mindspore_available():
    import mindspore
    from mindspore import ops
    from mindnlp.transformers import (
        GitForCausalLM,
        GitModel,
        GitPreTrainedModel,
        GitVisionModel
    )


if is_vision_available():
    from PIL import Image

    from mindnlp.transformers import CLIPProcessor

class GitVisionModelTester:
    def __init__(
        self,
        parent,
        batch_size=12,
        image_size=32,
        patch_size=16,
        num_channels=3,
        is_training=True,
        hidden_size=32,
        projection_dim=32,
        num_hidden_layers=2,
        num_attention_heads=4,
        intermediate_size=37,
        dropout=0.1,
        attention_dropout=0.1,
        initializer_range=0.02,
        scope=None,
    ):
        self.parent = parent
        self.batch_size = batch_size
        self.image_size = image_size
        self.patch_size = patch_size
        self.num_channels = num_channels
        self.is_training = is_training
        self.hidden_size = hidden_size
        self.projection_dim = projection_dim
        self.num_hidden_layers = num_hidden_layers
        self.num_attention_heads = num_attention_heads
        self.intermediate_size = intermediate_size
        self.dropout = dropout
        self.attention_dropout = attention_dropout
        self.initializer_range = initializer_range
        self.scope = scope

        # in ViT, the seq length equals the number of patches + 1 (we add 1 for the [CLS] token)
        num_patches = (image_size // patch_size) ** 2
        self.seq_length = num_patches + 1

    def prepare_config_and_inputs(self):
        pixel_values = floats_tensor([self.batch_size, self.num_channels, self.image_size, self.image_size])
        config = self.get_config()

        return config, pixel_values

    def get_config(self):
        return GitVisionConfig(
            image_size=self.image_size,
            patch_size=self.patch_size,
            num_channels=self.num_channels,
            hidden_size=self.hidden_size,
            projection_dim=self.projection_dim,
            num_hidden_layers=self.num_hidden_layers,
            num_attention_heads=self.num_attention_heads,
            intermediate_size=self.intermediate_size,
            dropout=self.dropout,
            attention_dropout=self.attention_dropout,
            initializer_range=self.initializer_range,
        )

    def create_and_check_model(self, config, pixel_values):
        model = GitVisionModel(config=config)
        model.set_train(False)
        with mindspore.no_grad():
            result = model(pixel_values)
        # expected sequence length = num_patches + 1 (we add 1 for the [CLS] token)
        image_size = (self.image_size, self.image_size)
        patch_size = (self.patch_size, self.patch_size)
        num_patches = (image_size[1] // patch_size[1]) * (image_size[0] // patch_size[0])
        self.parent.assertEqual(result.last_hidden_state.shape, (self.batch_size, num_patches + 1, self.hidden_size))

    def prepare_config_and_inputs_for_common(self):
        config_and_inputs = self.prepare_config_and_inputs()
        config, pixel_values = config_and_inputs
        inputs_dict = {"pixel_values": pixel_values}
        return config, inputs_dict


@require_mindspore
class GitVisionModelTest(ModelTesterMixin, unittest.TestCase):
    """
    Here we also overwrite some of the tests of test_modeling_common.py, as GIT does not use input_ids, inputs_embeds,
    attention_mask and seq_length.
    """

    all_model_classes = (GitVisionModel,) if is_mindspore_available() else ()
    fx_compatible = True
    test_pruning = False
    test_resize_embeddings = False
    test_head_masking = False

    def setUp(self):
        self.model_tester = GitVisionModelTester(self)
        self.config_tester = ConfigTester(self, config_class=GitVisionConfig, has_text_modality=False, hidden_size=37)

    def test_config(self):
        self.config_tester.run_common_tests()

    @unittest.skip(reason="GIT does not use inputs_embeds")
    def test_inputs_embeds(self):
        pass

    def test_model_common_attributes(self):
        config, _ = self.model_tester.prepare_config_and_inputs_for_common()

        for model_class in self.all_model_classes:
            model = model_class(config)
            self.assertIsInstance(model.get_input_embeddings(), (nn.Module))
            x = model.get_output_embeddings()
            self.assertTrue(x is None or isinstance(x, nn.Linear))

    def test_forward_signature(self):
        config, _ = self.model_tester.prepare_config_and_inputs_for_common()

        for model_class in self.all_model_classes:
            model = model_class(config)
            signature = inspect.signature(model.forward)
            # signature.parameters is an OrderedDict => so arg_names order is deterministic
            arg_names = [*signature.parameters.keys()]

            expected_arg_names = ["pixel_values"]
            self.assertListEqual(arg_names[:1], expected_arg_names)

    def test_model(self):
        config_and_inputs = self.model_tester.prepare_config_and_inputs()
        self.model_tester.create_and_check_model(*config_and_inputs)

    def test_training(self):
        pass

    def test_training_gradient_checkpointing(self):
        pass

    @unittest.skip(
        reason="This architecure seem to not compute gradients properly when using GC, check: https://github.com/huggingface/transformers/pull/27124"
    )
    def test_training_gradient_checkpointing_use_reentrant(self):
        pass

    @unittest.skip(
        reason="This architecure seem to not compute gradients properly when using GC, check: https://github.com/huggingface/transformers/pull/27124"
    )
    def test_training_gradient_checkpointing_use_reentrant_false(self):
        pass

    @unittest.skip(reason="GitVisionModel has no base class and is not available in MODEL_MAPPING")
    def test_save_load_fast_init_from_base(self):
        pass

    @unittest.skip(reason="GitVisionModel has no base class and is not available in MODEL_MAPPING")
    def test_save_load_fast_init_to_base(self):
        pass

    @slow
    def test_model_from_pretrained(self):
        model_name = "microsoft/git-base"
        model = GitVisionModel.from_pretrained(model_name)
        self.assertIsNotNone(model)


class GitModelTester:
    def __init__(
        self,
        parent,
        num_channels=3,
        image_size=32,
        patch_size=16,
        batch_size=13,
        text_seq_length=7,
        is_training=True,
        use_input_mask=True,
        use_labels=True,
        vocab_size=99,
        hidden_size=32,
        num_hidden_layers=2,
        num_attention_heads=4,
        intermediate_size=37,
        hidden_act="gelu",
        hidden_dropout_prob=0.1,
        attention_probs_dropout_prob=0.1,
        max_position_embeddings=512,
        type_vocab_size=16,
        initializer_range=0.02,
        num_labels=3,
        scope=None,
    ):
        self.parent = parent
        self.num_channels = num_channels
        self.image_size = image_size
        self.patch_size = patch_size
        self.batch_size = batch_size
        self.text_seq_length = text_seq_length
        self.is_training = is_training
        self.use_input_mask = use_input_mask
        self.use_labels = use_labels
        self.vocab_size = vocab_size
        self.hidden_size = hidden_size
        self.num_hidden_layers = num_hidden_layers
        self.num_attention_heads = num_attention_heads
        self.intermediate_size = intermediate_size
        self.hidden_act = hidden_act
        self.hidden_dropout_prob = hidden_dropout_prob
        self.attention_probs_dropout_prob = attention_probs_dropout_prob
        self.max_position_embeddings = max_position_embeddings
        self.type_vocab_size = type_vocab_size
        self.initializer_range = initializer_range
        self.num_labels = num_labels
        self.scope = scope

        # make sure the BOS, EOS and PAD tokens are within the vocab
        self.bos_token_id = vocab_size - 1
        self.eos_token_id = vocab_size - 1
        self.pad_token_id = vocab_size - 1

        # for GIT, the sequence length is the sum of the text and patch tokens, + 1 due to the CLS token
        self.seq_length = self.text_seq_length + int((self.image_size / self.patch_size) ** 2) + 1

    def prepare_config_and_inputs(self):
        input_ids = ids_tensor([self.batch_size, self.text_seq_length], self.vocab_size)

        input_mask = None
        if self.use_input_mask:
            input_mask = random_attention_mask([self.batch_size, self.text_seq_length])

        pixel_values = floats_tensor([self.batch_size, self.num_channels, self.image_size, self.image_size])

        config = self.get_config()

        return config, input_ids, input_mask, pixel_values

    def get_config(self):
        """
        Returns a tiny configuration by default.
        """
        return GitConfig(
            vision_config={
                "num_channels": self.num_channels,
                "image_size": self.image_size,
                "patch_size": self.patch_size,
                "hidden_size": self.hidden_size,
                "projection_dim": 32,
                "num_hidden_layers": self.num_hidden_layers,
                "num_attention_heads": self.num_attention_heads,
            },
            vocab_size=self.vocab_size,
            hidden_size=self.hidden_size,
            num_hidden_layers=self.num_hidden_layers,
            num_attention_heads=self.num_attention_heads,
            intermediate_size=self.intermediate_size,
            hidden_act=self.hidden_act,
            hidden_dropout_prob=self.hidden_dropout_prob,
            attention_probs_dropout_prob=self.attention_probs_dropout_prob,
            max_position_embeddings=self.max_position_embeddings,
            initializer_range=self.initializer_range,
            bos_token_id=self.bos_token_id,
            eos_token_id=self.eos_token_id,
            pad_token_id=self.pad_token_id,
        )

    def create_and_check_model(self, config, input_ids, input_mask, pixel_values):
        model = GitModel(config=config)
        model.set_train(False)

        # inference with pixel values
        result = model(input_ids, attention_mask=input_mask, pixel_values=pixel_values)

        self.parent.assertEqual(result.last_hidden_state.shape, (self.batch_size, self.seq_length, self.hidden_size))

        # inference without pixel values
        result = model(input_ids, attention_mask=input_mask)
        result = model(input_ids)

        self.parent.assertEqual(
            result.last_hidden_state.shape, (self.batch_size, self.text_seq_length, self.hidden_size)
        )

    def create_and_check_for_causal_lm(self, config, input_ids, input_mask, pixel_values):
        model = GitForCausalLM(config=config)
        model.set_train(False)

        # inference with pixel values
        result = model(input_ids, attention_mask=input_mask, pixel_values=pixel_values)
        self.parent.assertEqual(result.logits.shape, (self.batch_size, self.seq_length, self.vocab_size))

        # inference without pixel values
        result = model(input_ids, attention_mask=input_mask)
        result = model(input_ids)
        self.parent.assertEqual(result.logits.shape, (self.batch_size, self.text_seq_length, self.vocab_size))

        # training
        result = model(input_ids, attention_mask=input_mask, pixel_values=pixel_values, labels=input_ids)
        self.parent.assertEqual(result.logits.shape, (self.batch_size, self.seq_length, self.vocab_size))
        self.parent.assertEqual(result.logits.shape, (self.batch_size, self.seq_length, self.vocab_size))
        self.parent.assertEqual(result.loss.shape, ())
        self.parent.assertTrue(result.loss.item() > 0)

    def _test_beam_search_generate(self, config, input_ids, input_mask, pixel_values):
        model = GitForCausalLM(config=config)
        model.set_train(False)

        # generate
        generated_ids = model.generate(
            input_ids,
            attention_mask=input_mask,
            pixel_values=pixel_values,
            do_sample=False,
            max_length=20,
            num_beams=2,
            num_return_sequences=2,
        )

        self.parent.assertEqual(generated_ids.shape, (self.batch_size * 2, 20))

    def _test_batched_generate_captioning(self, config, input_ids, input_mask, pixel_values):
        model = GitForCausalLM(config=config)
        model.set_train(False)

        # generate
        generated_ids = model.generate(
            input_ids=None,  # captioning -> no input_ids
            attention_mask=None,
            pixel_values=pixel_values,
            do_sample=False,
            max_length=20,
            num_beams=2,
            num_return_sequences=2,
        )

        self.parent.assertEqual(generated_ids.shape, (self.batch_size * 2, 20))

    def prepare_config_and_inputs_for_common(self):
        config_and_inputs = self.prepare_config_and_inputs()

        (
            config,
            input_ids,
            input_mask,
            pixel_values,
        ) = config_and_inputs

        inputs_dict = {
            "input_ids": input_ids,
            "attention_mask": input_mask,
            "pixel_values": pixel_values,
        }

        return config, inputs_dict


@require_mindspore
class GitModelTest(ModelTesterMixin, GenerationTesterMixin, PipelineTesterMixin, unittest.TestCase):
    all_model_classes = (GitModel, GitForCausalLM) if is_mindspore_available() else ()
    all_generative_model_classes = (GitForCausalLM,) if is_mindspore_available() else ()
    fx_compatible = False
    test_torchscript = False

    # special case for GitForCausalLM model
    def _prepare_for_class(self, inputs_dict, model_class, return_labels=False):
        inputs_dict = super()._prepare_for_class(inputs_dict, model_class, return_labels=return_labels)

        if return_labels:
            if model_class in get_values(MODEL_FOR_CAUSAL_LM_MAPPING):
                inputs_dict["labels"] = mindspore.zeros(
                    (self.model_tester.batch_size, self.model_tester.text_seq_length),
                    dtype=mindspore.int64,
                )
        return inputs_dict

    def setUp(self):
        self.model_tester = GitModelTester(self)
        self.config_tester = ConfigTester(self, config_class=GitConfig, hidden_size=37)

    def test_config(self):
        self.config_tester.run_common_tests()

    def test_model(self):
        config_and_inputs = self.model_tester.prepare_config_and_inputs()
        self.model_tester.create_and_check_model(*config_and_inputs)

    def test_for_causal_lm(self):
        config_and_inputs = self.model_tester.prepare_config_and_inputs()
        self.model_tester.create_and_check_for_causal_lm(*config_and_inputs)

    def test_beam_search_generate(self):
        config_and_inputs = self.model_tester.prepare_config_and_inputs()
        self.model_tester._test_beam_search_generate(*config_and_inputs)

    def test_batched_generate_captioning(self):
        config_and_inputs = self.model_tester.prepare_config_and_inputs()
        self.model_tester._test_batched_generate_captioning(*config_and_inputs)

    def test_model_various_embeddings(self):
        config_and_inputs = self.model_tester.prepare_config_and_inputs()
        for type in ["absolute", "relative_key", "relative_key_query"]:
            config_and_inputs[0].position_embedding_type = type
            self.model_tester.create_and_check_model(*config_and_inputs)

    @slow
    def test_model_from_pretrained(self):
        model_name = "microsoft/git-base"
        model = GitModel.from_pretrained(model_name)
        self.assertIsNotNone(model)

    @unittest.skip(reason="GIT has pixel values as additional input")
    def test_beam_search_generate_dict_outputs_use_cache(self):
        pass

    @unittest.skip(reason="GIT has pixel values as additional input")
    def test_contrastive_generate(self):
        pass

    @unittest.skip(reason="GIT has pixel values as additional input")
    def test_contrastive_generate_dict_outputs_use_cache(self):
        pass

    @unittest.skip(reason="GIT has pixel values as additional input")
    def test_greedy_generate_dict_outputs_use_cache(self):
        pass


@require_mindspore
@require_vision
@slow
class GitModelIntegrationTest(unittest.TestCase):
    def test_forward_pass(self):
        processor = GitProcessor.from_pretrained("microsoft/git-base")
        model = GitForCausalLM.from_pretrained("microsoft/git-base")


        image = Image.open("./tests/fixtures/tests_samples/COCO/000000039769.png")
        inputs = processor(images=image, text="hello world", return_tensors="pt")

        with mindspore.no_grad():
            outputs = model(**inputs)

        expected_shape = mindspore.Size((1, 201, 30522))
        self.assertEqual(outputs.logits.shape, expected_shape)
        expected_slice = mindspore.tensor(
            [[-0.9514, -0.9512, -0.9507], [-0.5454, -0.5453, -0.5453], [-0.8862, -0.8857, -0.8848]],
        )
        self.assertTrue(np.allclose(outputs.logits[0, :3, :3].asnumpy(), expected_slice.asnumpy(), atol=1e-4))

    def test_inference_image_captioning(self):
        processor = GitProcessor.from_pretrained("microsoft/git-base")
        model = GitForCausalLM.from_pretrained("microsoft/git-base")

        image = Image.open("./tests/fixtures/tests_samples/COCO/000000039769.png")
        inputs = processor(images=image, return_tensors="pt")
        pixel_values = inputs.pixel_values

        outputs = model.generate(
            pixel_values=pixel_values, max_length=20, output_scores=True, return_dict_in_generate=True
        )
        generated_caption = processor.batch_decode(outputs.sequences, skip_special_tokens=True)[0]

        expected_shape = mindspore.Size((1, 9))
        self.assertEqual(outputs.sequences.shape, expected_shape)
        self.assertEqual(generated_caption, "two cats laying on a pink blanket")
        self.assertTrue(outputs.scores[-1].shape, expected_shape)
        expected_slice = mindspore.tensor([[-0.8805, -0.8803, -0.8799]])
        self.assertTrue(np.allclose(outputs.scores[-1][0, :3].asnumpy(), expected_slice.asnumpy(), atol=1e-4))

    def test_visual_question_answering(self):
        processor = GitProcessor.from_pretrained("microsoft/git-base-textvqa")
        model = GitForCausalLM.from_pretrained("microsoft/git-base-textvqa")

        # prepare image
        file_path = hf_hub_download(repo_id="nielsr/textvqa-sample", filename="bus.png", repo_type="dataset")
        image = Image.open(file_path).convert("RGB")
        inputs = processor(images=image, return_tensors="pt")
        pixel_values = inputs.pixel_values

        # prepare question
        question = "what does the front of the bus say at the top?"
        input_ids = processor(text=question, add_special_tokens=False).input_ids
        input_ids = [processor.tokenizer.cls_token_id] + input_ids
        input_ids = mindspore.tensor(input_ids).unsqueeze(0)

        generated_ids = model.generate(pixel_values=pixel_values, input_ids=input_ids, max_length=20)
        generated_caption = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]

        expected_shape = mindspore.Size((1, 15))
        self.assertEqual(generated_ids.shape, expected_shape)
        self.assertEqual(generated_caption, "what does the front of the bus say at the top? special")

    def test_batched_generation(self):
        processor = GitProcessor.from_pretrained("microsoft/git-base-coco")
        model = GitForCausalLM.from_pretrained("microsoft/git-base-coco")


        # create batch of size 2
        image = Image.open("./tests/fixtures/tests_samples/COCO/000000039769.png")
        inputs = processor(images=[image, image], return_tensors="pt")
        pixel_values = inputs.pixel_values

        # we have to prepare `input_ids` with the same batch size as `pixel_values`
        start_token_id = model.config.bos_token_id
        input_ids = mindspore.tensor([[start_token_id], [start_token_id]])
        generated_ids = model.generate(pixel_values=pixel_values, input_ids=input_ids, max_length=50)
        generated_captions = processor.batch_decode(generated_ids, skip_special_tokens=True)

        self.assertEqual(generated_captions, ["two cats sleeping on a pink blanket next to remotes."] * 2)
