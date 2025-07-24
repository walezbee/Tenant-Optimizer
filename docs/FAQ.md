# FAQ — Tenant Optimizer

**Q: Is this safe to use on production tenants?**  
A: Yes, all destructive/upgrade actions require explicit approval and are logged.

**Q: How does Tenant Optimizer stay up-to-date with Azure changes?**  
A: It uses AI prompts and rule updates, and can be updated with new patterns as Azure evolves.

**Q: What permissions are required?**  
A: The app requires Reader access to scan, and Contributor/Owner access for delete/upgrade actions.

**Q: Can I define my own orphaned or deprecated resource patterns?**  
A: Yes, the agent logic and prompts are extensible.

**Q: How is data secured?**  
A: All secrets in Key Vault, RBAC enforced, tenant data isolated in Cosmos DB.