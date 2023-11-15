# syntax=docker/dockerfile:1

FROM python:3.10-slim

# Set the working directory
WORKDIR /usr/src/app

# Copy the Python script and requirements file into the container
COPY ./distilbert_on_mrpc.py ./ 
COPY ./requirements.txt ./ 

# Install Python dependencies from requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Use CMD to run your script, without specifying ENTRYPOINT
CMD ["python3", "./distilbert_on_mrpc.py"]
