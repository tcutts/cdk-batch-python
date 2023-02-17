FROM --platform=linux/amd64 amazonlinux:latest as build
RUN yum -y install autoheader automake gcc make perl-Data-Dumper tar bzip2 zlib-devel bzip2-devel xz-devel curl-devel openssl-devel ncurses-devel
WORKDIR /tmp
RUN /usr/bin/curl -L https://github.com/samtools/samtools/releases/download/1.16.1/samtools-1.16.1.tar.bz2 | tar jxf -
WORKDIR /tmp/samtools-1.16.1
RUN autoreconf 2> /dev/null
RUN ./configure --prefix=/usr/local/samtools
RUN make
RUN make install

FROM --platform=linux/amd64 amazonlinux:latest
RUN yum -y install xz-libs bzip2 zlib openssl-libs
COPY --from=build /usr/local/samtools /usr/local
