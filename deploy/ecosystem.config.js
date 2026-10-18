const path = require("path");

const projectDir = path.resolve(__dirname, "..");
const botDir = path.join(projectDir, "bot_tg");

module.exports = {
  apps: [
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
