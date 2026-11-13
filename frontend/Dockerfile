FROM node:20-alpine AS builder
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

RUN mkdir -p public/mediapipe/wasm && \
    cp -r node_modules/@mediapipe/tasks-vision/wasm/* public/mediapipe/wasm/

ARG REACT_APP_API_URL
ENV REACT_APP_API_URL=$REACT_APP_API_URL
ARG REACT_APP_USERNAME
ENV REACT_APP_USERNAME=$REACT_APP_USERNAME
ARG REACT_APP_PASSWORD
ENV REACT_APP_PASSWORD=$REACT_APP_PASSWORD
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/build /usr/share/nginx/html

COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]