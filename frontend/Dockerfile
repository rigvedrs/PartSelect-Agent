FROM node:22.12.0-slim

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --silent

COPY . .

ENV REACT_APP_API_URL=http://localhost:8000

EXPOSE 3000
CMD ["npm", "start"]
