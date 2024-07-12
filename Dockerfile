#specify base image (base images are provided by DockerHub)
FROM python:latest

#set up working directory
WORKDIR /app

#copy necessary files to working directory "."
COPY utilities.py pokerBot.py requirements.txt .env .

#install dependencies in requirements.txt through pip for this container's python installation
RUN pip install -r requirements.txt

#specify port number to be exposed if needed (like for a web app)
#EXPOSE 5000

#specify the default command to run when the docker container is started from the image (so the command to run the application)
CMD ["python", "./pokerBot.py"]


#RUN is used to execute commands during the build process of a Docker image (so here it will download requirements.txt into the image so that any container created from the image will have the dependencies)
#CMD is used to specify the default command to run when a Docker container is started from the image.

#to build the image from this dockerfile, run "docker build -t image_name ." (the "." is the location of the dockerfile)

#to create and run a docker container, do "docker run -p port_num (optional) -d (optional) --name container_name image_name"