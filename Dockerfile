# Use the official Node.js 18 image.
# https://hub.docker.com/_/node
FROM node:20

# Create and change to the app directory.
WORKDIR /usr/src/app

COPY package.json ./

RUN npm install --only=production

COPY . ./

EXPOSE 8080
EXPOSE 443

CMD [ "npm", "start" ]

