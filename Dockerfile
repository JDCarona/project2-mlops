# syntax=docker/dockerfile:1

FROM python:3.10-slim

WORKDIR /usr/src/app

COPY ./distilbert_on_mrpc.py ./ 
RUN pip install scipy
RUN pip install scikit-learn
RUN pip install wandb
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install transformers 
RUN pip install pytorch_lightning==1.9.5 
RUN pip install datasets
CMD ["python3", "./distilbert_on_mrpc.py"]
