from database.db_manager import DatabaseManager, logger


def main():
    """Main function to set up the database and insert initial data."""
    logger.info("Starting database setup...")

    db_manager = DatabaseManager()

    if not db_manager.create_database():
        logger.error("Failed to create database")
        return False

    if db_manager.config.products_path:
        if not db_manager.insert_products_from_json():
            logger.error("Failed to insert products")
            return False

    logger.info("Database setup completed successfully")
    return True


if __name__ == "__main__":
    main()
