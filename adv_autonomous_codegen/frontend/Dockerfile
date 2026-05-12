FROM node:20-alpine

WORKDIR /app

# Copy package definition and install dependencies
COPY package.json ./
RUN npm install

# Copy frontend code
COPY . .

# Expose Vite's default port and run on 0.0.0.0 so it's accessible from the host
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host"]
