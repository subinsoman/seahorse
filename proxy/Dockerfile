# ────────────────────────────────────────────────────
# Legacy build on Node 6 (Alpine)
# ────────────────────────────────────────────────────
FROM node:6.11-alpine

# 1) Install Git via Alpine’s apk (no update step needed)
RUN apk add --no-cache git

# 2) Clean npm’s cache and remove any broken staging folder
RUN npm cache clean --force \
 && rm -rf /usr/local/lib/node_modules/.staging

# 3) Globally install the last Webpack + externals versions that support Node 6
RUN npm install -g webpack@3.12.0 webpack-node-externals@1.7.2

# 4) Set working directory
WORKDIR /opt/docker

# 5) Copy only your manifest files and install all dependencies
#    (using a wildcard so it works with or without a lockfile)
COPY package*.json ./
RUN npm config set registry=http://registry.npmjs.org/ \
 && npm install

# 6) Copy the rest of your source, build, then optionally clean up
COPY . .
RUN npm run build \
 && rm -rf app

# 7) Default command
CMD ["npm", "start"]

