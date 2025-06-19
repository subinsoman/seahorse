FROM jupyter/minimal-notebook:python-3.7

USER root

# Install pip for Python 3.7
RUN wget -q https://bootstrap.pypa.io/pip/3.7/get-pip.py && python3.7 get-pip.py

# Copy requirements.txt into the container
COPY requirements.txt /tmp/requirements.txt

# Install packages from requirements.txt
RUN pip3 install --no-cache-dir $(grep -v '^pika==' /tmp/requirements.txt)

# Install a version of pika compatible with Python 3.7
RUN pip3 install pika==1.1.0

# Install jupyter_contrib_nbextensions
RUN pip3 install jupyter_contrib_nbextensions

# Install and enable the Python 3 kernel
RUN python3 -m ipykernel install --name python3 --display-name "Python 3"

# Copy necessary files
COPY code/forwarding_kernel/ /usr/local/share/jupyter/kernels/pyspark/
COPY code/rabbit_mq_client.py \
     code/socket_forwarder.py \
     code/utils.py \
     code/notebook_server_client.py \
     /usr/local/share/jupyter/kernels/pyspark/
COPY code/forwarding_kernel_py/ /usr/local/share/jupyter/kernels/forwarding_kernel_py/
COPY code/forwarding_kernel_r/ /usr/local/share/jupyter/kernels/forwarding_kernel_r/

# Copy seahorse_notebook_path for Python 3.7
COPY seahorse_notebook_path /usr/local/lib/python3.7/site-packages

COPY jupyter_notebook_config.py /home/jovyan/.jupyter
COPY wmcontents /opt/conda/lib/python3.7/site-packages/wmcontents

# Copy additional files
COPY seahorse_notebook_path /opt/conda/lib/python3.7/site-packages/
COPY execute_saver /opt/conda/lib/python3.7/site-packages/execute_saver
COPY headless_notebook_handler.py /opt/conda/lib/python3.7/site-packages/headless_notebook_handler/

# Create a custom jupyter_notebook_config.py
RUN echo "c.NotebookApp.kernel_info_timeout = 60" >> /home/jovyan/.jupyter/jupyter_notebook_config.py
RUN echo "c.NotebookApp.allow_root = True" >> /home/jovyan/.jupyter/jupyter_notebook_config.py
RUN echo "c.NotebookApp.token = ''" >> /home/jovyan/.jupyter/jupyter_notebook_config.py  # Disable token authentication
RUN echo "c.NotebookApp.disable_check_xsrf = True" >> /home/jovyan/.jupyter/jupyter_notebook_config.py  # Disable XSRF checks

COPY custom-start.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/custom-start.sh

EXPOSE 8888

ENV MQ_USER=guest
ENV MQ_PASS=guest
ENV HEARTBEAT_INTERVAL=2.0
ENV MISSED_HEARTBEAT_LIMIT=30

ENTRYPOINT ["tini", "--"]
CMD ["custom-start.sh"]
