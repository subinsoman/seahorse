# Copyright (c) 2016, CodiLime Inc.
FROM hortonworks/cloudbreak-uaa:3.6.0

ENV H2_VERSION 1.4.192

# build-essential gcc ruby-dev rubygems libssl-dev packages are needed by cf-uaac
# get moreutils for sponge

#RUN echo "deb [check-valid-until=no] http://cdn-fastly.deb.debian.org/debian jessie main" > /etc/apt/sources.list.d/jessie.list
#RUN echo "deb [check-valid-until=no] http://archive.debian.org/debian jessie-backports main" > /etc/apt/sources.list.d/jessie-backports.list
# RUN sed -i '/deb http:\/\/deb.debian.org\/debian jessie-updates main/d' /etc/apt/sources.list
#RUN sed -i '/deb http:\/\/\(deb\|httpredir\).debian.org\/debian jessie.* main/d' /etc/apt/sources.list

# --- use the real archive for everything ---
RUN echo "deb http://archive.debian.org/debian/ jessie main" \
      > /etc/apt/sources.list.d/jessie.list && \
    echo "deb http://archive.debian.org/debian/ jessie-backports main" \
      > /etc/apt/sources.list.d/jessie-backports.list

# Remove any other jessie lines that might still be present
RUN sed -i '/jessie.*main/d' /etc/apt/sources.list


#RUN apt-get -o Acquire::Check-Valid-Until=false update && \
#    DEBIAN_FRONTEND=noninteractive apt-get install -y ruby ruby-dev rubygems mailutils build-essential openssl zip

RUN apt-get -o Acquire::Check-Valid-Until=false -o Debug::pkgAcquire=1 update && \
    DEBIAN_FRONTEND=noninteractive \
    apt-get -o Debug::pkgAcquire=1 \
            -o Debug::pkgProblemResolver=1 \
            -y install ruby ruby-dev rubygems mailutils build-essential openssl zip

RUN gem install public_suffix -v '<3.0' && \
    gem install cf-uaac -v 4.0.0

RUN apt-get install -y moreutils && \
    apt-get clean && \
    apt-get autoremove && \
    rm -rf /var/lib/apt/lists/*

# Exim4 should be able to send mails to whole internet
ADD update-exim4.conf.conf /etc/exim4/
ADD messages.properties /opt/WEB-INF/classes/
ADD uaa.yml /opt/uaa/

# Add h2 driver to cloudfoundry identity uaa
# Add messages.properties with new information for activation email
# H2 is needed in /opt/ since SQL script use it.
RUN mkdir -p /opt/WEB-INF/lib/ && \
    wget http://repo2.maven.org/maven2/com/h2database/h2/${H2_VERSION}/h2-${H2_VERSION}.jar \
        -O /opt/WEB-INF/lib/h2-${H2_VERSION}.jar && \
    cp /opt/WEB-INF/lib/h2-${H2_VERSION}.jar /opt/ && \
    cd /opt/ && zip -r /tomcat/webapps/ROOT.war WEB-INF/ && \
    rm -Rf /opt/WEB-INF && \
    mv /tomcat/webapps/ROOT.war /tomcat/webapps/authorization.war && \
    rm -Rf /uaa/uaa.yml

ADD docker-dummy-authorization.sh replace_envs.sh adjust_admin_account.sh update_admin_user.sql \
 create_admin_user.sql check_if_database_ready.sql /opt/
RUN chmod +x /opt/docker-dummy-authorization.sh /opt/replace_envs.sh /opt/adjust_admin_account.sh
# New run.sh starts postfix MTA
ADD run.sh /tmp/
RUN chmod +x /tmp/run.sh

