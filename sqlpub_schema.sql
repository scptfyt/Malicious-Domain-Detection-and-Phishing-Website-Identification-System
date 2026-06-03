SET NAMES utf8mb4;
USE `mysystem0521`;
SET FOREIGN_KEY_CHECKS = 0;

CREATE TABLE IF NOT EXISTS `user` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `username` VARCHAR(64) NOT NULL,
  `password_hash` VARCHAR(255) NOT NULL,
  `role` VARCHAR(32) NOT NULL DEFAULT 'user',
  `email` VARCHAR(128) NULL,
  `status` VARCHAR(16) NOT NULL DEFAULT 'active',
  `active_model_id` INT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_user_username` (`username`),
  KEY `ix_user_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `domain_sample` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `domain` VARCHAR(255) NOT NULL,
  `url` VARCHAR(1024) NULL,
  `label` VARCHAR(32) NOT NULL,
  `sample_type` VARCHAR(32) NOT NULL,
  `source` VARCHAR(128) NULL,
  `is_trainable` TINYINT(1) NOT NULL DEFAULT 1,
  `remark` VARCHAR(255) NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_domain_sample_domain` (`domain`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `model_info` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `model_name` VARCHAR(64) NOT NULL,
  `model_type` VARCHAR(64) NOT NULL,
  `version` VARCHAR(32) NOT NULL,
  `file_path` VARCHAR(255) NOT NULL,
  `feature_type` VARCHAR(64) NOT NULL,
  `storage_type` VARCHAR(32) NOT NULL DEFAULT 'file',
  `model_blob` LONGBLOB NULL,
  `owner_id` INT NULL,
  `is_active` TINYINT(1) NOT NULL DEFAULT 0,
  `remark` VARCHAR(255) NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_model_info_owner_id` (`owner_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `training_task` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `model_type` VARCHAR(64) NOT NULL,
  `dataset_size` INT NOT NULL DEFAULT 0,
  `train_config` TEXT NOT NULL,
  `status` VARCHAR(32) NOT NULL DEFAULT 'pending',
  `started_at` DATETIME NULL,
  `finished_at` DATETIME NULL,
  `created_by` INT NULL,
  `log_text` TEXT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_training_task_created_by` (`created_by`),
  CONSTRAINT `fk_training_task_created_by_user`
    FOREIGN KEY (`created_by`) REFERENCES `user` (`id`)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `evaluation_metric` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `model_id` INT NOT NULL,
  `task_id` INT NULL,
  `accuracy` DOUBLE NULL,
  `precision_value` DOUBLE NULL,
  `recall_value` DOUBLE NULL,
  `f1_value` DOUBLE NULL,
  `auc_value` DOUBLE NULL,
  `confusion_matrix` TEXT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_evaluation_metric_model_id` (`model_id`),
  KEY `ix_evaluation_metric_task_id` (`task_id`),
  CONSTRAINT `fk_evaluation_metric_model_info`
    FOREIGN KEY (`model_id`) REFERENCES `model_info` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_evaluation_metric_training_task`
    FOREIGN KEY (`task_id`) REFERENCES `training_task` (`id`)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `feature_record` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `sample_id` INT NOT NULL,
  `domain_length` INT NULL,
  `entropy_value` DOUBLE NULL,
  `digit_ratio` DOUBLE NULL,
  `hyphen_count` INT NULL,
  `dot_count` INT NULL,
  `subdomain_count` INT NULL,
  `sequence_length` INT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_feature_record_sample_id` (`sample_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE `feature_record`
  ADD CONSTRAINT `fk_feature_record_domain_sample`
  FOREIGN KEY (`sample_id`) REFERENCES `domain_sample` (`id`)
  ON DELETE CASCADE ON UPDATE CASCADE;

CREATE TABLE IF NOT EXISTS `detection_record` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NULL,
  `input_text` VARCHAR(1024) NOT NULL,
  `parsed_domain` VARCHAR(255) NOT NULL,
  `predict_label` VARCHAR(32) NOT NULL,
  `risk_score` DOUBLE NOT NULL,
  `risk_level` VARCHAR(32) NOT NULL,
  `model_id` INT NULL,
  `detect_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `explain_text` TEXT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_detection_record_user_id` (`user_id`),
  KEY `ix_detection_record_model_id` (`model_id`),
  KEY `ix_detection_record_detect_time` (`detect_time`),
  CONSTRAINT `fk_detection_record_user`
    FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `fk_detection_record_model_info`
    FOREIGN KEY (`model_id`) REFERENCES `model_info` (`id`)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `operation_log` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NULL,
  `action_type` VARCHAR(64) NOT NULL,
  `target_type` VARCHAR(64) NULL,
  `target_id` VARCHAR(64) NULL,
  `detail` TEXT NULL,
  `ip_address` VARCHAR(64) NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_operation_log_user_id` (`user_id`),
  CONSTRAINT `fk_operation_log_user`
    FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `review_feedback` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `record_id` INT NOT NULL,
  `reviewer_id` INT NULL,
  `review_result` VARCHAR(32) NOT NULL,
  `correct_label` VARCHAR(32) NULL,
  `comment` TEXT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_review_feedback_record_id` (`record_id`),
  KEY `ix_review_feedback_reviewer_id` (`reviewer_id`),
  CONSTRAINT `fk_review_feedback_detection_record`
    FOREIGN KEY (`record_id`) REFERENCES `detection_record` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_review_feedback_user`
    FOREIGN KEY (`reviewer_id`) REFERENCES `user` (`id`)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS = 1;
