# Copyright 2022 Huawei Technologies Co., Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ============================================================================
"""
Abstract class for Pretrained models.
"""
# pylint: disable=E1128
import os
from typing import Union, Optional
from mindspore.train.serialization import load_checkpoint, load_param_into_net
from mindspore import nn, ops
from mindspore import log as logger

from mindnlp.configs import HF_MODEL_URL_BASE
from mindnlp.utils.download import cached_path
from mindnlp.abc.configs import PreTrainedConfig
from mindnlp.abc.mixins import CellUtilMixin, GenerationMixin


class PreTrainedModel(nn.Cell, CellUtilMixin, GenerationMixin):
    """
    Abstract class for Pretrained models
    """
    config_class = None
    pretrained_model_archive_map = {}
    base_model_prefix = ""

    def __init__(self, config):
        super().__init__(config)
        # Save config in model
        self.config = config

    def post_init(self):
        """
        A method executed at the end of each Transformer model initialization, to execute code that needs the model's
        modules properly initialized (such as weight initialization).

        self.init_model_weights()
        self._backward_compatibility_gradient_checkpointing()
        """
        raise NotImplementedError

    def init_model_weights(self):
        """
        initialize model weights.
        """
        raise NotImplementedError

    @property
    def base_model(self):
        """
        to get base_model
        """
        return getattr(self, self.base_model_prefix, self)

    def get_input_embeddings(self) -> "nn.Cell":
        """
        Returns the model's input embeddings.

        Returns:
            :obj:`nn.Cell`: A mindspore cell mapping vocabulary to hidden states.
        """
        base_model = getattr(self, self.base_model_prefix, self)
        if base_model is not self:
            return base_model.get_input_embeddings()
        raise NotImplementedError

    def set_input_embeddings(self, value: "nn.Cell"):
        """
        Set model's input embeddings.

        Args:
            value (:obj:`nn.Cell`): A mindspore cell mapping vocabulary to hidden states.
        """
        base_model = getattr(self, self.base_model_prefix, self)
        if base_model is not self:
            base_model.set_input_embeddings(value)
        else:
            raise NotImplementedError

    def resize_position_embeddings(self, new_num_position_embeddings: int):
        """
        resize the model position embeddings if necessary
        """
        raise NotImplementedError(
            f"`resize_position_embeddings` is not implemented for {self.__class__}`. To implement it, you should "
            f"overwrite this method in the class {self.__class__}"
        )

    def get_output_embeddings(self):
        """ Get model's output embeddings
            Return None if the model doesn't have output embeddings
        """
        return None  # Overwrite for models with output embeddings

    def get_position_embeddings(self):
        """
        get the model position embeddings if necessary
        """
        raise NotImplementedError(
            f"`get_position_embeddings` is not implemented for {self.__class__}`. To implement it, you should "
            f"overwrite this method in the class {self.__class__}"
        )

    def tie_weights(self):
        """
        Make sure we are sharing the input and output embeddings.
        If you need this feature,
        you need to get it yourself output Add the output you need to add to the embeddings function_ Embedding layer,
        otherwise you cannot
        """
        output_embeddings = self.get_output_embeddings()
        if output_embeddings is not None:
            self._tie_or_clone_weights(output_embeddings, self.get_input_embeddings())

    def _tie_or_clone_weights(self, output_embeddings, input_embeddings):
        """ Tie or clone module weights depending of weither we are using or not
        """

        output_embeddings.embedding_table = input_embeddings.embedding_table

        if hasattr(output_embeddings, "bias") and output_embeddings.bias is not None:
            output_embeddings.bias.data = ops.pad(
                output_embeddings.bias.data,
                (0, output_embeddings.embedding_table.shape[0] - output_embeddings.bias.shape[0]),
                "constant",
                0,
            )
        if hasattr(output_embeddings, "out_features") and hasattr(input_embeddings, "num_embeddings"):
            output_embeddings.out_features = input_embeddings.num_embeddings

    def resize_token_embeddings(self, new_num_tokens=None):
        """ Resize input token embeddings matrix of the model if new_num_tokens != config.vocab_size.
        Take care of tying weights embeddings afterwards if the model class has a `tie_weights()` method.

        Arguments:

            new_num_tokens: (`optional`) int:
                New number of tokens in the embedding matrix.
                Increasing the size will add newly initialized vectors at the end.
                Reducing the size will remove vectors from the end.
                If not provided or None:
                    does nothing and just returns a pointer to
                    the input tokens ``mindspore.nn.Embeddings`` Module of the model.

        Return: ``mindspore.nn.Embeddings``
            Pointer to the input tokens Embeddings Module of the model
        """
        base_model = getattr(self, self.base_model_prefix, self)  # get the base model if needed
        model_embeds = base_model.resize_tokenizer_embeddings(new_num_tokens)
        if new_num_tokens is None:
            return model_embeds

        # Update base model and current model config
        self.config.vocab_size = new_num_tokens
        base_model.vocab_size = new_num_tokens

        # Tie weights again if needed

        return model_embeds

    def resize_tokenizer_embeddings(self, new_num_tokens):
        """
        Obtain a new embedding layer or use the original one without updating it.
        """
        old_embeddings = self.get_input_embeddings()
        new_embeddings = self._get_resized_embeddings(old_embeddings, new_num_tokens)
        self.set_input_embeddings(new_embeddings)
        return self.get_input_embeddings()

    def _get_resized_embeddings(self, old_embeddings, new_num_tokens=None):
        """ Build a resized Embedding Module from a provided token Embedding Module.
            Increasing the size will add newly initialized vectors at the end
            Reducing the size will remove vectors from the end

        Args:
            new_num_tokens: (`optional`) int
                New number of tokens in the embedding matrix.
                Increasing the size will add newly initialized vectors at the end
                Reducing the size will remove vectors from the end
                If not provided or None: return the provided token Embedding Module.
        Return: ``mindspore.nn.Embeddings``
            Pointer to the resized Embedding Module or the old Embedding Module if new_num_tokens is None
        """
        if new_num_tokens is None:
            return old_embeddings

        old_num_tokens, old_embedding_dim = old_embeddings.embedding_table.shape
        if old_num_tokens == new_num_tokens:
            return old_embeddings

        # Build new embeddings
        new_embeddings = nn.Embedding(new_num_tokens, old_embedding_dim)

        # initialize all new embeddings (in particular added tokens)
        self._init_weights(new_embeddings)

        # Copy word embeddings from the previous weights
        num_tokens_to_copy = min(old_num_tokens, new_num_tokens)
        new_embeddings.embedding_table.data[:num_tokens_to_copy, :] = old_embeddings.embedding_table.data[
                                                                      :num_tokens_to_copy, :]

        return new_embeddings

    def save(self, save_dir: Union[str, os.PathLike]):
        "save pretrain model"
        raise NotImplementedError

    @classmethod
    def load(cls, pretrained_model_name_or_path: Optional[Union[str, os.PathLike]],
             *args, **kwargs):
        """
        Load a pre-trained checkpoint from a pre-trained model file or url,
        download and cache the pre-trained model file if model name in model list.

        Params:
            pretrained_model_name_or_path:
        """
        return cls.from_pretrained(pretrained_model_name_or_path, args, kwargs)


    @classmethod
    def from_pretrained(cls, pretrained_model_name_or_path, *model_args, **kwargs):
        """from_pretrained"""
        config = kwargs.pop("config", None)
        state_dict = kwargs.pop("state_dict", None)
        cache_dir = kwargs.pop("cache_dir", None)
        from_pt = kwargs.pop("from_pt", False)
        force_download = kwargs.pop("force_download", False)
        resume_download = kwargs.pop("resume_download", False)
        proxies = kwargs.pop("proxies", None)
        local_files_only = kwargs.pop("local_files_only", False)

        # Load config if we don't provide a configuration
        if not isinstance(config, PreTrainedConfig):
            config_path = config if config is not None else pretrained_model_name_or_path
            config, model_kwargs = cls.config_class.from_pretrained(
                config_path,
                *model_args,
                from_pt=from_pt,
                cache_dir=cache_dir,
                return_unused_kwargs=True,
                force_download=force_download,
                resume_download=resume_download,
                proxies=proxies,
                local_files_only=local_files_only,
                **kwargs,
            )
        else:
            model_kwargs = kwargs

        folder_name = None
        # Load model
        if pretrained_model_name_or_path is not None:
            if pretrained_model_name_or_path in cls.pretrained_model_archive_map and not from_pt:
                archive_file = cls.pretrained_model_archive_map[pretrained_model_name_or_path]
                folder_name = pretrained_model_name_or_path
            elif os.path.isdir(pretrained_model_name_or_path):
                archive_file = os.path.join(pretrained_model_name_or_path, "mindspore_model.ckpt")
            elif os.path.isfile(pretrained_model_name_or_path):
                archive_file = pretrained_model_name_or_path
            elif from_pt:
                archive_file = HF_MODEL_URL_BASE.format(pretrained_model_name_or_path)
                folder_name = pretrained_model_name_or_path
            else:
                raise ValueError(f'not found model of {pretrained_model_name_or_path}.')

            # redirect to the cache, if necessary
            try:
                resolved_archive_file = str(cached_path(
                    archive_file,
                    cache_dir=cache_dir,
                    proxies=proxies,
                    folder_name=folder_name
                )[0])
            except EnvironmentError as exc:
                if pretrained_model_name_or_path in cls.pretrained_model_archive_map:
                    msg = f"Couldn't reach server at '{archive_file}' to download pretrained weights."
                else:
                    format1 = ", ".join(cls.pretrained_model_archive_map.keys())
                    format2 = ["mindspore.ckpt"]
                    msg = (
                        f"Model name '{pretrained_model_name_or_path}' "
                        f"was not found in model name list ({format1}). "
                        f"We assumed '{archive_file}' "
                        f"was a path or url to model weight files named one of {format2} but "
                        f"couldn't find any such file at this path or url."
                    )
                raise EnvironmentError(msg) from exc

            if resolved_archive_file == archive_file:
                logger.info("loading weights file %s", archive_file)
            else:
                logger.info("loading weights file %s from cache at %s", archive_file, resolved_archive_file)
        else:
            raise ValueError("the argument 'pretrained_model_name_or_path' should be "
                             "a string of model name or checkpoint path, but got 'None'.")

        # Instantiate model.
        model = cls(config, *model_args, **model_kwargs)

        if from_pt:
            resolved_archive_file = cls.convert_torch_to_mindspore(resolved_archive_file, prefix=cls.base_model_prefix)

        if state_dict is None:
            try:
                state_dict = load_checkpoint(resolved_archive_file)
            except Exception as exc:
                raise OSError(
                    f"Unable to load weights from mindspore checkpoint file '{resolved_archive_file}'. "
                ) from exc

        load_param_into_net(model, state_dict)

        return model