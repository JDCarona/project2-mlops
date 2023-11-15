# project2-mlops
This is a school Assignment for the course MLOPS.

Prerequisities:
This guide is optimized for debian-based distros.
You can also run it on docker playground.

- Have a Wandb account and the API Key ready.


1. Clone the repository in to your system.
2. Find the file ```Dockerfile``` which should at the root folder and run the following command:
```sudo docker build -t run_distilbert_training .```
3. Run a docker container with this image with the following command, your wandb API key and the hyperparameters of your choice:

```sudo docker run run_distilbert_training python3 ./distilbert_on_mrpc.py --api_key YOUR_WANDB_API_KEY --learning_rate 6.991860954982597e-05 --train_batch_size 256 --optimizer_type Adam```
4. If you go to your list of wandb.ai projects, a new project called "Project_2-Docker_experiment" will be initialized. There you can find the all the experiment logs

Here is a list of passable hyperparameters:

- '--learning_rate', dest='learning_rate', type=float
- '--adam_epsilon', dest='adam_epsilon', type=float
- '--warmup_steps', dest='warmup_steps', type=float
- '--weight_decay', dest='weight_decay', type=float
- '--train_batch_size', dest='train_batch_size', type=int
- '--eval_batch_size', dest='eval_batch_size', type=int
- '--eval_splits', dest='eval_splits', type=int
- '--momentum', dest='momentum', type=float
- '--optimizer_type', dest='optimizer_type', type=str
- '--max_seq_length', dest='max_seq_length', type=int
- '--api_key', dest='api_key', type=str


