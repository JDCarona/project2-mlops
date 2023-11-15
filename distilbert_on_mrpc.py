# -*- coding: utf-8 -*-
"""DistilBERT_on_MRPC.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/18JZ03w9Xyvx6P_DBneDP7jQSZ1gNR3XY

Finetunes [distilbert-base-uncased](https://huggingface.co/distilbert-base-uncased) on [MRPC](https://huggingface.co/datasets/glue/viewer/mrpc/train). Adapted from a [PyTorch Lightning example](https://lightning.ai/docs/pytorch/1.9.5/notebooks/lightning_examples/text-transformers.html).
"""

# Commented out IPython magic to ensure Python compatibility.
# %load_ext autotime

from datetime import datetime
from typing import Optional

import datasets
import torch
from torch.utils.data import DataLoader
from transformers import (
    AutoConfig,
    AutoModelForSequenceClassification,
    AutoTokenizer,
    get_linear_schedule_with_warmup,
)
from pytorch_lightning import LightningDataModule, LightningModule, Trainer, seed_everything

class GLUEDataModule(LightningDataModule):
    task_text_field_map = {
        "cola": ["sentence"],
        "sst2": ["sentence"],
        "mrpc": ["sentence1", "sentence2"],
        "qqp": ["question1", "question2"],
        "stsb": ["sentence1", "sentence2"],
        "mnli": ["premise", "hypothesis"],
        "qnli": ["question", "sentence"],
        "rte": ["sentence1", "sentence2"],
        "wnli": ["sentence1", "sentence2"],
        "ax": ["premise", "hypothesis"],
    }

    glue_task_num_labels = {
        "cola": 2,
        "sst2": 2,
        "mrpc": 2,
        "qqp": 2,
        "stsb": 1,
        "mnli": 3,
        "qnli": 2,
        "rte": 2,
        "wnli": 2,
        "ax": 3,
    }

    loader_columns = [
        "datasets_idx",
        "input_ids",
        "token_type_ids",
        "attention_mask",
        "start_positions",
        "end_positions",
        "labels",
    ]

    def __init__(
        self,
        model_name_or_path: str,
        task_name: str = "mrpc",
        max_seq_length: int = 128,
        train_batch_size: int = 32,
        eval_batch_size: int = 32,
        **kwargs,
    ):
        super().__init__()
        self.model_name_or_path = model_name_or_path
        self.task_name = task_name
        self.max_seq_length = max_seq_length
        self.train_batch_size = train_batch_size
        self.eval_batch_size = eval_batch_size

        self.text_fields = self.task_text_field_map[task_name]
        self.num_labels = self.glue_task_num_labels[task_name]
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name_or_path, use_fast=True)

    def setup(self, stage: str):
        self.dataset = datasets.load_dataset("glue", self.task_name)

        for split in self.dataset.keys():
            self.dataset[split] = self.dataset[split].map(
                self.convert_to_features,
                batched=True,
                remove_columns=["label"],
            )
            self.columns = [c for c in self.dataset[split].column_names if c in self.loader_columns]
            self.dataset[split].set_format(type="torch", columns=self.columns)

        self.eval_splits = [x for x in self.dataset.keys() if "validation" in x]

    def prepare_data(self):
        datasets.load_dataset("glue", self.task_name)
        AutoTokenizer.from_pretrained(self.model_name_or_path, use_fast=True)

    def train_dataloader(self):
        return DataLoader(self.dataset["train"], batch_size=self.train_batch_size, shuffle=True)

    def val_dataloader(self):
        if len(self.eval_splits) == 1:
            return DataLoader(self.dataset["validation"], batch_size=self.eval_batch_size)
        elif len(self.eval_splits) > 1:
            return [DataLoader(self.dataset[x], batch_size=self.eval_batch_size) for x in self.eval_splits]

    def test_dataloader(self):
        if len(self.eval_splits) == 1:
            return DataLoader(self.dataset["test"], batch_size=self.eval_batch_size)
        elif len(self.eval_splits) > 1:
            return [DataLoader(self.dataset[x], batch_size=self.eval_batch_size) for x in self.eval_splits]

    def convert_to_features(self, example_batch, indices=None):
        # Either encode single sentence or sentence pairs
        if len(self.text_fields) > 1:
            texts_or_text_pairs = list(zip(example_batch[self.text_fields[0]], example_batch[self.text_fields[1]]))
        else:
            texts_or_text_pairs = example_batch[self.text_fields[0]]

        # Tokenize the text/text pairs
        features = self.tokenizer.batch_encode_plus(
            texts_or_text_pairs, max_length=self.max_seq_length, pad_to_max_length=True, truncation=True
        )

        # Rename label to labels to make it easier to pass to model forward
        features["labels"] = example_batch["label"]

        return features

class GLUETransformer(LightningModule):
    def __init__(
        self,
        model_name_or_path: str,
        num_labels: int,
        task_name: str,
        learning_rate: float = 2e-5,
        adam_epsilon: float = 1e-8,
        warmup_steps: int = 0,
        weight_decay: float = 0.0,
        train_batch_size: int = 32,
        eval_batch_size: int = 32,
        eval_splits: Optional[list] = None,
        momentum: float = 0.5,
        optimizer_type = 'Adam',
        **kwargs,
    ):
        super().__init__()

        self.save_hyperparameters()

        self.config = AutoConfig.from_pretrained(model_name_or_path, num_labels=num_labels)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name_or_path, config=self.config)
        self.metric = datasets.load_metric(
            "glue", self.hparams.task_name, experiment_id=datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
        )
        print()

    def forward(self, **inputs):
        return self.model(**inputs)

    def training_step(self, batch, batch_idx):
        outputs = self(**batch)
        loss = outputs[0]
        return loss

    def validation_step(self, batch, batch_idx, dataloader_idx=0):
        outputs = self(**batch)
        val_loss, logits = outputs[:2]

        if self.hparams.num_labels > 1:
            preds = torch.argmax(logits, axis=1)
        elif self.hparams.num_labels == 1:
            preds = logits.squeeze()

        labels = batch["labels"]

        return {"loss": val_loss, "preds": preds, "labels": labels}

    def validation_epoch_end(self, outputs):
        if self.hparams.task_name == "mnli":
            for i, output in enumerate(outputs):
                # matched or mismatched
                split = self.hparams.eval_splits[i].split("_")[-1]
                preds = torch.cat([x["preds"] for x in output]).detach().cpu().numpy()
                labels = torch.cat([x["labels"] for x in output]).detach().cpu().numpy()
                loss = torch.stack([x["loss"] for x in output]).mean()
                self.log(f"val_loss_{split}", loss, prog_bar=True)
                split_metrics = {
                    f"{k}_{split}": v for k, v in self.metric.compute(predictions=preds, references=labels).items()
                }
                self.log_dict(split_metrics, prog_bar=True)
            return loss

        preds = torch.cat([x["preds"] for x in outputs]).detach().cpu().numpy()
        labels = torch.cat([x["labels"] for x in outputs]).detach().cpu().numpy()
        loss = torch.stack([x["loss"] for x in outputs]).mean()
        self.log("val_loss", loss, prog_bar=True)
        self.log_dict(self.metric.compute(predictions=preds, references=labels), prog_bar=True)

    def configure_optimizers(self):
        """Prepare optimizer and schedule (linear warmup and decay)"""
        model = self.model
        no_decay = ["bias", "LayerNorm.weight"]
        optimizer_grouped_parameters = [
            {
                "params": [p for n, p in model.named_parameters() if not any(nd in n for nd in no_decay)],
                "weight_decay": self.hparams.weight_decay,
            },
            {
                "params": [p for n, p in model.named_parameters() if any(nd in n for nd in no_decay)],
                "weight_decay": 0.0,
            },
        ]

        optimizer = None
        if self.hparams.optimizer_type == 'Adam':
          optimizer = torch.optim.AdamW(optimizer_grouped_parameters, lr=self.hparams.learning_rate, eps=self.hparams.adam_epsilon)
        elif self.hparams.optimizer_type == 'SGD':
          optimizer = torch.optim.SGD(
            optimizer_grouped_parameters,
            lr=self.hparams.learning_rate,
            momentum=self.hparams.momentum,  # You can adjust momentum as needed
            weight_decay=self.hparams.weight_decay
          )


        scheduler = get_linear_schedule_with_warmup(
            optimizer,
            num_warmup_steps=self.hparams.warmup_steps,
            num_training_steps=self.trainer.estimated_stepping_batches,
        )
        scheduler = {"scheduler": scheduler, "interval": "step", "frequency": 1}
        return [optimizer], [scheduler]

    # def configure_optimizers(self):
    #   model = self.model
    #   no_decay = ["bias", "LayerNorm.weight"]
    #   optimizer_grouped_parameters = [
    #       {
    #           "params": [p for n, p in model.named_parameters() if not any(nd in n for nd in no_decay)],
    #           "weight_decay": self.hparams.weight_decay,
    #       },
    #       {
    #           "params": [p for n, p in model.named_parameters() if any(nd in n for nd in no_decay)],
    #           "weight_decay": 0.0,
    #       },
    #   ]

    #   # Define the SGD optimizer with appropriate parameters
    #   optimizer = torch.optim.SGD(
    #       optimizer_grouped_parameters,
    #       lr=self.hparams.learning_rate,
    #       momentum=self.hparams.momentum,  # You can adjust momentum as needed
    #       weight_decay=self.hparams.weight_decay
    #   )

    #   scheduler = get_linear_schedule_with_warmup(
    #       optimizer,
    #       num_warmup_steps=self.hparams.warmup_steps,
    #       num_training_steps=self.trainer.estimated_stepping_batches,
    #   )
    #   scheduler = {"scheduler": scheduler, "interval": "step", "frequency": 1}
    #   return [optimizer], [scheduler]

# import torch
# from pytorch_lightning import Trainer, seed_everything

# # Define the hyperparameter grids
# learning_rate_grid = [1e-4, 1e-5, 1e-6]
# train_batch_size_grid = [32, 64, 128]
# optimizer_type_grid = ['Adam', 'SGD']

# # Initialize variables to track the best parameters and performance
# best_params = None
# best_validation_accuracy = 0.0

# # Function to perform grid search
# def run_grid_search():
#     total_runs = 0
#     global best_params
#     global best_validation_accuracy
#     for learning_rate in learning_rate_grid:
#         for train_batch_size in train_batch_size_grid:
#             for optimizer_type in optimizer_type_grid:
#                 if total_runs >= 20:
#                   return
#                 print('Run', total_runs + 1)
#                 print(f"Running with learning_rate={learning_rate}, train_batch_size={train_batch_size}, optimizer_type={optimizer_type}")

#                 # Update the hyperparameters
#                 learning_rate = learning_rate
#                 train_batch_size = train_batch_size
#                 optimizer_type = optimizer_type

#                 # Set up the data module
#                 dm = GLUEDataModule(
#                     model_name_or_path="distilbert-base-uncased",
#                     task_name="mrpc",
#                 )
#                 dm.setup("fit")

#                 # Set up the model
#                 model = GLUETransformer(
#                     model_name_or_path="distilbert-base-uncased",
#                     num_labels=dm.num_labels,
#                     eval_splits=dm.eval_splits,
#                     task_name=dm.task_name,
#                     learning_rate=learning_rate,
#                     train_batch_size=train_batch_size,
#                     optimizer_type=optimizer_type
#                 )

#                 # Set up the trainer
#                 trainer = Trainer(
#                     max_epochs=3,
#                     accelerator="auto",
#                     gpus=1 if torch.cuda.is_available() else 0,
#                 )

#                 # Train the model
#                 trainer.fit(model, datamodule=dm)
#                 total_runs += 1
#                 print(trainer.callback_metrics)

#                 # Update the best parameters if needed based on validation accuracy
#                 validation_accuracy = trainer.callback_metrics["accuracy"]
#                 if validation_accuracy > best_validation_accuracy:
#                     best_validation_accuracy = validation_accuracy
#                     best_params = {
#                         "learning_rate": learning_rate,
#                         "train_batch_size": train_batch_size,
#                         "optimizer_type": optimizer_type
#                     }
#                     print(f"New best parameters found: {best_params}, Validation Accuracy: {best_validation_accuracy}")


# # Set a seed for reproducibility
# seed_everything(42)

# # Run the grid search
# # run_grid_search()

# # Print the best parameters and their validation performance
# print("Best Parameters:")
# print(best_params)
# print("Best Validation Accuracy:", best_validation_accuracy)

seed_everything(42)

import argparse
import wandb
from pytorch_lightning.loggers import WandbLogger

parser = argparse.ArgumentParser()
parser.add_argument('--learning_rate', dest='learning_rate', type=float)
parser.add_argument('--adam_epsilon', dest='adam_epsilon', type=float)
parser.add_argument('--warmup_steps', dest='warmup_steps', type=float)
parser.add_argument('--weight_decay', dest='weight_decay', type=float)
parser.add_argument('--train_batch_size', dest='train_batch_size', type=int)
parser.add_argument('--eval_batch_size', dest='eval_batch_size', type=int)
parser.add_argument('--eval_splits', dest='eval_splits', type=int)
parser.add_argument('--momentum', dest='momentum', type=float)
parser.add_argument('--optimizer_type', dest='optimizer_type', type=str)
parser.add_argument('--max_seq_length', dest='max_seq_length', type=int)
parser.add_argument('--api_key', dest='api_key', type=str)
args = parser.parse_args()

wandb.login(key=args.api_key)


config_inputs = {
    'learning_rate': args.learning_rate if args.learning_rate is not None else 2e-5,
    'adam_epsilon': args.adam_epsilon if args.adam_epsilon is not None else 1e-8,
    'warmup_steps': args.warmup_steps if args.warmup_steps is not None else 0,
    'weight_decay': args.weight_decay if args.weight_decay is not None else 0.0,
    'train_batch_size': args.train_batch_size if args.train_batch_size is not None else 32,
    'eval_batch_size': args.eval_batch_size if args.eval_batch_size is not None else 32,
    'eval_splits': args.eval_splits if args.eval_splits is not None else None,
    'momentum': args.momentum if args.momentum is not None else 0.5,
    'optimizer_type': args.optimizer_type if args.optimizer_type is not None else 'Adam',
    'max_seq_length': args.max_seq_length if args.max_seq_length is not None else 128
}

print(config_inputs)

# Set up the data module
dm = GLUEDataModule(
    model_name_or_path="distilbert-base-uncased",
    task_name="mrpc",
    max_seq_length=config_inputs['max_seq_length'],
    train_batch_size=config_inputs['train_batch_size'],
    eval_batch_size=config_inputs['eval_batch_size'],
)
dm.setup("fit")

# Set up the model
model = GLUETransformer(
    model_name_or_path="distilbert-base-uncased",
    num_labels=dm.num_labels,
    eval_splits=dm.eval_splits,
    task_name=dm.task_name,
    learning_rate=config_inputs['learning_rate'],
    train_batch_size=config_inputs['train_batch_size'],
    optimizer_type=config_inputs['optimizer_type'],
    adam_epsilon=config_inputs['adam_epsilon'],
    warmup_steps=config_inputs['warmup_steps'],
    weight_decay=config_inputs['weight_decay'],
    eval_batch_size=config_inputs['eval_batch_size'],
    momentum=config_inputs['momentum'],
    report_to="wandb"
)

wandb.init(
            # set the wandb project where this run will be logged
            project="Project_2-Docker_experiment",
            # track hyperparameters and run metadata
            config=config_inputs,
            name=f"GLUETransformer_split-max_seq_length-{config_inputs['max_seq_length']}-learning_rate-{config_inputs['learning_rate']}-weight_decay-{config_inputs['weight_decay']}-momentum-{config_inputs['momentum']}-warmup_steps-{config_inputs['warmup_steps']}-adam_epsilon-{config_inputs['adam_epsilon']}-optimizer_type-{config_inputs['optimizer_type']}"
        )
wandb_logger = WandbLogger(log_model='all')

# Set up the trainer
trainer = Trainer(
    max_epochs=3,
    accelerator="auto",
    gpus=1 if torch.cuda.is_available() else 0,
    logger=wandb_logger
)


# Train the model
trainer.fit(model, datamodule=dm)

# import torch
# from pytorch_lightning import Trainer, seed_everything
# import optuna

# # Define the objective function for Optuna to optimize
# def objective(trial):
#     # Sample hyperparameters
#     learning_rate = trial.suggest_loguniform("learning_rate", 1e-5, 1e-2)
#     train_batch_size = trial.suggest_categorical("train_batch_size", [32, 64, 128, 256])
#     optimizer_type = trial.suggest_categorical("optimizer_type", ['Adam', 'SGD'])

#     # Set up the data module
#     dm = GLUEDataModule(
#         model_name_or_path="distilbert-base-uncased",
#         task_name="mrpc",
#     )
#     dm.setup("fit")

#     # Set up the model with the sampled hyperparameters
#     model = GLUETransformer(
#         model_name_or_path="distilbert-base-uncased",
#         num_labels=dm.num_labels,
#         eval_splits=dm.eval_splits,
#         task_name=dm.task_name,
#         learning_rate=learning_rate,
#         train_batch_size=train_batch_size,
#         optimizer_type = optimizer_type,
#     )

#     # Set up the trainer
#     trainer = Trainer(
#         max_epochs=3,
#         accelerator="auto",
#         gpus=1 if torch.cuda.is_available() else 0,
#     )

#     # Train the model
#     trainer.fit(model, datamodule=dm)

#     # Return the validation accuracy to optimize (maximize)
#     return trainer.callback_metrics.get("accuracy", 0.0)

# # Set a seed for reproducibility
# seed_everything(42)

# # Create a study and optimize the objective function
# study = optuna.create_study(direction="maximize")
# study.optimize(objective, n_trials=30)

# # Print the best parameters and their validation performance
# print("Number of finished trials: ", len(study.trials))
# print("Best trial:")
# trial = study.best_trial
# print("Value: ", trial.value)
# print("Params: ")
# for key, value in trial.params.items():
#     print(f"    {key}: {value}")