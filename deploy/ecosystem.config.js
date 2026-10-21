const path = require("path");

const projectDir = path.resolve(__dirname, "..");
const botDir = path.join(projectDir, "bot_tg");

module.exports = {
  apps: [
    {
      name: "marilobanka-web",
      cwd: botDir,
      script: path.join(botDir, ".venv/bin/gunicorn"),
      args: "--bind 127.0.0.1:18082 --workers 1 --threads 4 --access-logfile - --error-logfile - web:create_app()",
      interpreter: "none",
      autorestart: true,
      restart_delay: 5000,
      env: {
        PYTHONUNBUFFERED: "1",
      },
    },
    {
      name: "marilobanka-bot",
      cwd: botDir,
      script: "main.py",
      interpreter: path.join(botDir, ".venv/bin/python"),
      autorestart: true,
      restart_delay: 5000,
      env: {
        PYTHONUNBUFFERED: "1",
      },
    },
  ],
};
