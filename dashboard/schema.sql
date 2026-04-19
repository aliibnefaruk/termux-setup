CREATE DATABASE IF NOT EXISTS termux_dashboard CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'termux'@'localhost' IDENTIFIED BY 'Termux@Dash2026!';
GRANT ALL PRIVILEGES ON termux_dashboard.* TO 'termux'@'localhost';
FLUSH PRIVILEGES;

USE termux_dashboard;

CREATE TABLE IF NOT EXISTS phones (
  id INT AUTO_INCREMENT PRIMARY KEY,
  phone_id VARCHAR(100) UNIQUE NOT NULL,
  name VARCHAR(100) DEFAULT '',
  user VARCHAR(50) NOT NULL,
  tunnel_port INT NOT NULL,
  status ENUM('connected','active','stale','offline') DEFAULT 'offline',
  public_key TEXT,
  ssh_password VARCHAR(255) DEFAULT NULL,
  last_seen DATETIME,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS phone_stats (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  phone_id VARCHAR(100) NOT NULL,
  battery_level INT DEFAULT NULL,
  battery_status VARCHAR(20) DEFAULT '',
  memory_percent INT DEFAULT NULL,
  storage_percent INT DEFAULT NULL,
  cpu_idle BIGINT DEFAULT NULL,
  tunnel_status VARCHAR(20) DEFAULT 'DOWN',
  process_count INT DEFAULT NULL,
  net_rx BIGINT DEFAULT 0,
  net_tx BIGINT DEFAULT 0,
  recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_phone_time (phone_id, recorded_at)
);

CREATE TABLE IF NOT EXISTS invites (
  id INT AUTO_INCREMENT PRIMARY KEY,
  token VARCHAR(32) UNIQUE NOT NULL,
  tunnel_port INT NOT NULL,
  used BOOLEAN DEFAULT FALSE,
  used_by VARCHAR(100) DEFAULT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  used_at DATETIME DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS command_log (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  phone_id VARCHAR(100) NOT NULL,
  command TEXT NOT NULL,
  output TEXT,
  exit_code INT DEFAULT NULL,
  executed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_phone_cmd (phone_id, executed_at)
);

SHOW TABLES;

-- Migration: add ssh_password to existing installations
ALTER TABLE phones ADD COLUMN IF NOT EXISTS ssh_password VARCHAR(255) DEFAULT NULL;
