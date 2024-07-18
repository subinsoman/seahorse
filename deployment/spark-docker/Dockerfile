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
    libopenblas-base \
    libopenblas-dev \
    && apt-get clean \
    && apt-get autoremove \
    && rm -rf /var/lib/apt/lists/*

# Setup passwordless SSH
RUN ssh-keygen -q -N "" -t rsa -f /root/.ssh/id_rsa
RUN cp /root/.ssh/id_rsa.pub /root/.ssh/authorized_keys

# Install Spark
ENV SPARK_PACKAGE spark-$SPARK_VERSION-bin-hadoop$HADOOP_VERSION
ENV SPARK_HOME /opt/spark-$SPARK_VERSION
ENV PATH $PATH:$SPARK_HOME/bin
RUN wget -q -O - \
  "https://archive.apache.org/dist/spark/spark-$SPARK_VERSION/$SPARK_PACKAGE.tgz" \
  | gunzip \
  | tar x -C /tmp/ \
  && mv /tmp/$SPARK_PACKAGE $SPARK_HOME \
  && rm -rf $SPARK_HOME/examples $SPARK_HOME/ec2 \
  && rm -rf $SPARK_HOME/lib/spark-examples*.jar

# Install Miniconda and Python 3.7
RUN wget -q -O /tmp/Miniconda3-latest-Linux-x86_64.sh \
    https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh && \
    bash /tmp/Miniconda3-latest-Linux-x86_64.sh -f -b -p /opt/conda && \
    rm /tmp/Miniconda3-latest-Linux-x86_64.sh

# Install Python packages
RUN /opt/conda/bin/conda install --yes python=3.7 && \
    /opt/conda/bin/conda install --yes \
    'tornado' 'ipykernel' 'jupyter_client' 'pandas' 'matplotlib' \
    'scipy' 'seaborn' 'scikit-learn' 'libgfortran' && \
    /opt/conda/bin/conda clean --all --yes



# Flag to use old g++ ABI (necessary for compilation of r-igraph package)
RUN mkdir -p /root/.R && \
    echo "CXXFLAGS+=-D_GLIBCXX_USE_CXX11_ABI=0" >> /root/.R/Makevars

ENV PATH $PATH:/opt/conda/bin

COPY startup.sh /opt/
RUN chown root.root /opt/startup.sh && chmod 700 /opt/startup.sh

ENTRYPOINT [ "/opt/startup.sh" ]
CMD [ "-d" ]