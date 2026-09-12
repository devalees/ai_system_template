FROM node:20-alpine

WORKDIR /app

# Install dependencies first for optimal layer caching
COPY package*.json ./
RUN npm install

# Copy source code
COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev"]
