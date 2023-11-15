# syntax=docker/dockerfile:1

FROM ubuntu:latest

# Install Python and Pip
RUN apt-get update && apt-get install -y python3 python3-pip

# Set the working directory
WORKDIR /usr/app/src

# Copy the Python script and requirements file into the container
COPY ./distilbert_on_mrpc.py ./ 
COPY ./requirements.txt ./ 

# Install Python dependencies from requirements.txt
RUN python3 -m pip install --verbose -r requirements.txt

# Use CMD to run your script, without specifying ENTRYPOINT
CMD ["python3", "./distilbert_on_mrpc.py"]