FROM tensorflow/tensorflow:latest-gpu

#RUN apt-get update
#RUN apt-get install -y unzip graphviz curl musescore3

RUN pip install --upgrade pip

WORKDIR /app
COPY . /app/backend
COPY requirements.txt /app
RUN pip install --upgrade pip

RUN apt-get remove python3-blinker -y

RUN pip install -r /app/requirements.txt

# Hack to get around tensorflow-io issue - https://github.com/tensorflow/io/issues/1755
#RUN pip install tensorflow-io
#RUN pip uninstall -y tensorflow-io

EXPOSE 5000

#ENV PYTHONPATH="${PYTHONPATH}:/app"
CMD ["gunicorn", "-k", "eventlet", "-w", "1", "backend.app:app", "--bind", "0.0.0.0:5000"]