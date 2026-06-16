import asyncio
import logging
import sys
from auragrid import AsyncGridContext

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger("identity_sync_demo")

async def run_sync():
    """Demonstrates federated identity synchronization with the Identity MAS."""
    logger.info("Starting Federated Identity Synchronization Demo...")
    
    async with AsyncGridContext() as grid:
        # 1. Simulate fetching users from an external Active Directory / LDAP source
        external_users = [
            {"id": "alice@corp.local", "name": "Alice Admin", "groups": ["Domain Admins", "AuraGrid-FoundryAdmins"]},
            {"id": "bob@corp.local", "name": "Bob Builder", "groups": ["Developers", "AuraGrid-AppDevelopers"]},
            {"id": "charlie@corp.local", "name": "Charlie Clerk", "groups": ["Users", "AuraGrid-AppUsers"]}
        ]
        
        logger.info("Retrieved %d users from Active Directory.", len(external_users))
        
        # 2. Sync with AuraGrid Identity MAS
        for ext_user in external_users:
            user_id = ext_user["id"]
            logger.info("Syncing %s...", user_id)
            
            # Map AD groups to Grid Roles and ABAC Attributes
            target_roles = []
            attributes = {"Project": "Aura"}
            
            if "Domain Admins" in ext_user["groups"]:
                attributes["Clearance"] = "TopSecret"

            if "AuraGrid-FoundryAdmins" in ext_user["groups"]:
                target_roles.append("FoundryAdmin")
            if "AuraGrid-AppDevelopers" in ext_user["groups"]:
                target_roles.append("AppDeveloper")
            if "AuraGrid-AppUsers" in ext_user["groups"]:
                target_roles.append("AppUser")
                
            # Update the profile, roles, and attributes in the cell
            # await grid.identity.update_profile(user_id, display_name=ext_user["name"], attributes=attributes)
            # await grid.governance.set_user_roles(user_id, target_roles)
            
            logger.info("SUCCESS: Identity %s synchronized with roles: %s and attributes: %s", user_id, target_roles, attributes)

        logger.info("Identity synchronization complete. Enterprise users can now login via mTLS.")

if __name__ == "__main__":
    asyncio.run(run_sync())
