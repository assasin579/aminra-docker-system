FROM python:3.13-alpine
RUN pip install --no-cache-dir docker==7.1.0 prometheus_client==0.21.0
COPY exporter.py /exporter.py
EXPOSE 9417
CMD ["python", "-u", "/exporter.py"]
