"""
Test MongoDB connection functionality.
"""

import pytest
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError


class TestMongoDBConnection:
    """Test MongoDB connection and basic operations"""

    def test_mongodb_connection_when_enabled(self, use_mongodb, mongodb_config):
        """Test MongoDB connection when MongoDB is enabled in config"""
        if not use_mongodb:
            pytest.skip("MongoDB is disabled in configuration")
            
        if not mongodb_config:
            pytest.fail("MongoDB is enabled but no MongoDB configuration found")
            
        uri = mongodb_config.get("uri")
        if not uri:
            pytest.fail("MongoDB URI not found in configuration")
            
        try:
            # Create MongoDB client with shorter timeout for testing
            client = MongoClient(uri, serverSelectionTimeoutMS=5000)
            
            # Test connection by pinging the server
            client.admin.command('ping')
            
            # Test database access
            database_name = mongodb_config.get("database", "reviews")
            db = client[database_name]
            
            # Test collection access
            collection_name = mongodb_config.get("collection", "google_reviews")
            collection = db[collection_name]
            
            # Verify we can perform basic operations
            # Test insert and delete a dummy document
            test_doc = {"_id": "test_connection", "test": True}
            collection.insert_one(test_doc)
            
            # Verify document was inserted
            found_doc = collection.find_one({"_id": "test_connection"})
            assert found_doc is not None
            assert found_doc["test"] is True
            
            # Clean up test document
            collection.delete_one({"_id": "test_connection"})
            
            # Verify document was deleted
            found_doc = collection.find_one({"_id": "test_connection"})
            assert found_doc is None
            
            client.close()
            
        except ConnectionFailure as e:
            pytest.fail(f"Failed to connect to MongoDB: {e}")
        except ServerSelectionTimeoutError as e:
            pytest.fail(f"MongoDB server selection timeout: {e}")
        except Exception as e:
            pytest.fail(f"Unexpected error testing MongoDB: {e}")

    def test_mongodb_config_validation(self, use_mongodb, mongodb_config):
        """Test that MongoDB configuration is valid when enabled"""
        if not use_mongodb:
            pytest.skip("MongoDB is disabled in configuration")
            
        # Check required configuration fields
        assert "uri" in mongodb_config, "MongoDB URI is required"
        assert "database" in mongodb_config, "MongoDB database name is required"
        assert "collection" in mongodb_config, "MongoDB collection name is required"
        
        # Validate URI format
        uri = mongodb_config["uri"]
        assert uri.startswith("mongodb://") or uri.startswith("mongodb+srv://"), "Invalid MongoDB URI format"
        
        # Validate names are not empty
        assert mongodb_config["database"].strip(), "Database name cannot be empty"
        assert mongodb_config["collection"].strip(), "Collection name cannot be empty"

    def test_mongodb_skipped_when_disabled(self, use_mongodb):
        """Test that MongoDB tests are skipped when disabled"""
        if use_mongodb:
            pytest.skip("MongoDB is enabled, this test is for disabled state")
            
        # This test passes if we reach here, meaning MongoDB is properly disabled
        assert True