# Copyright (c) 2016, CodiLime Inc.
FROM ubuntu:24.04
ARG SPARK_VERSION
ARG HADOOP_VERSION

# Install packages
RUN sed -i 's/archive.ubuntu.com/kr.archive.ubuntu.com/g' /etc/apt/sources.list
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    build-essential \
    openjdk-11-jre \
    wget \
    curl \
    bzip2 \
    openssh-server \
    openssh-client \
    libsm6 \
    libcurl4-openssl-dev \
    libssl-dev \
    gfortran \
    liblapack-dev \
    liblapack3 \
    libopenblas-dev \
    krb5-user \
    && apt-get clean \
    && apt-get autoremove \
    && rm -rf /var/lib/apt/lists/*

# Setup passwordless SSH
RUN ssh-keygen -q -N "" -t rsa -f /root/.ssh/id_rsa
RUN cp /root/.ssh/id_rsa.pub /root/.ssh/authorized_keys

# Install Spark
ENV SPARK_PACKAGE=spark-$SPARK_VERSION-bin-hadoop$HADOOP_VERSION
ENV SPARK_HOME=/opt/spark-$SPARK_VERSION
ENV PATH=$PATH:$SPARK_HOME/bin
RUN wget -O - \
  "https://archive.apache.org/dist/spark/spark-$SPARK_VERSION/$SPARK_PACKAGE.tgz" \
  | tar -xz -C /tmp/ \
  && mv /tmp/$SPARK_PACKAGE $SPARK_HOME \
  && rm -rf $SPARK_HOME/examples $SPARK_HOME/ec2 \
  && rm -rf $SPARK_HOME/lib/spark-examples*.jar

#COPY rdd.py /opt/spark-2.1.1/python/pyspark/

# Download and add the latest Log4j2 jars (version 2.24.0)
#RUN wget https://repo1.maven.org/maven2/org/apache/logging/log4j/log4j-api/2.24.0/log4j-api-2.24.0.jar -P $SPARK_HOME/jars/ \
#  && wget https://repo1.maven.org/maven2/org/apache/logging/log4j/log4j-core/2.24.0/log4j-core-2.24.0.jar -P $SPARK_HOME/jars/ \
#  && wget https://repo1.maven.org/maven2/org/apache/logging/log4j/log4j-slf4j-impl/2.24.0/log4j-slf4j-impl-2.24.0.jar -P $SPARK_HOME/jars/ \
#  && wget https://repo1.maven.org/maven2/org/apache/logging/log4j/log4j-1.2-api/2.24.0/log4j-1.2-api-2.24.0.jar -P $SPARK_HOME/jars/

# Install Miniconda with Python 3.7
RUN wget -q -O /tmp/Miniconda3-py37_4.9.2-Linux-x86_64.sh \
    https://repo.anaconda.com/miniconda/Miniconda3-py37_4.9.2-Linux-x86_64.sh && \
    bash /tmp/Miniconda3-py37_4.9.2-Linux-x86_64.sh -f -b -p /opt/conda && \
    rm /tmp/Miniconda3-py37_4.9.2-Linux-x86_64.sh

# Configure conda channels
RUN /opt/conda/bin/conda config --add channels conda-forge

# Copy requirements.txt
COPY requirements.txt /tmp/requirements.txt

# Install Python packages
RUN /opt/conda/bin/pip install -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt

#COPY paths.py /opt/conda/lib/python3.7/site-packages/jupyter_core/
ENV PATH=$PATH:/opt/conda/bin

COPY startup.sh /opt/
RUN chown root.root /opt/startup.sh && chmod 700 /opt/startup.sh

ENTRYPOINT [ "/opt/startup.sh" ]
CMD [ "-d" ]

