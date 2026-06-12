from ldap3 import Server, Connection, ALL, SIMPLE, LEVEL, SUBTREE
import socket
import traceback
import pandas as pd
from datetime import datetime, timedelta
import random
import re

class ADConnector:
    def __init__(self, server, username, password):
        if not server.startswith('ldap://') and not server.startswith('ldaps://'):
            self.server_url = f"ldap://{server}"
        else:
            self.server_url = server
            
        self.username = username
        self.password = password
        self.conn = None
        self.server_obj = None
    
    def test_network_connection(self):
        """Test basic network connectivity to the server"""
        try:
            if self.server_url.startswith('ldap://'):
                host = self.server_url[7:]
            elif self.server_url.startswith('ldaps://'):
                host = self.server_url[8:]
            else:
                host = self.server_url
            
            if ':' in host:
                host, port_str = host.split(':')
                port = int(port_str)
            else:
                port = 389  # Default LDAP port
            
            print(f"Testing network connection to {host}:{port}")
        
            # Try to establish a socket connection
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)  # 3 second timeout
            result = sock.connect_ex((host, port))
            sock.close()
            
            if result == 0:
                print(f"Network connection successful to {host}:{port}")
                return True
            else:
                print(f"Network connection failed to {host}:{port} with error code {result}")
                return False
            
        except Exception as e:
            print(f"Network test failed: {str(e)}")
            return False
    
    def connect(self):
        """Connect to the Active Directory server"""
        # First test network connectivity
        if not self.test_network_connection():
            print("Network connectivity test failed. Check if server is reachable.")
            return False
            
        try:
            # Print connection details for debugging
            print(f"Attempting to connect to: {self.server_url}")
            print(f"With username: {self.username}")
            
            # Try different connection approaches
            
            try:
                print("Trying connection with SIMPLE authentication...")
                self.server_obj = Server(self.server_url, get_info=ALL)
                self.conn = Connection(
                    self.server_obj,
                    user=self.username,
                    password=self.password,
                    authentication=SIMPLE,
                    auto_bind=True
                )
                print("Connected successfully with SIMPLE authentication")
                return True
            except Exception as e:
                print(f"Connection failed with SIMPLE: {str(e)}")
                print(traceback.format_exc())
            
            return False
        
        except Exception as e:
            print(f"LDAP connection failed: {str(e)}")
            print(traceback.format_exc())
            return False
    
    def close(self):
        """Close the connection to the Active Directory server"""
        if self.conn:
            try:
                self.conn.unbind()
                print("Connection closed successfully")
            except Exception as e:
                print(f"Error closing connection: {str(e)}")
            finally:
                self.conn = None
    
    def list_base_dns(self):
        """List available base DNs to help troubleshoot"""
        if not self.conn:
            raise ConnectionError("Not connected to AD server. Call connect() first.")
        
        try:
            # Try to search the root DSE
            try:
                self.conn.search(
                    search_base='',
                    search_filter='(objectClass=*)',
                    search_scope=LEVEL,
                    attributes=['namingContexts']
                )
                
                naming_contexts = []
                
                if self.conn.entries:
                    entry = self.conn.entries[0]
                    if hasattr(entry, 'namingContexts'):
                        naming_contexts = entry.namingContexts.values
                
                return {
                    'naming_contexts': naming_contexts,
                    'default_naming_context': naming_contexts[0] if naming_contexts else None
                }
            except Exception as e:
                print(f"Error searching root DSE: {e}")
                # If that fails, try a different approach
                return {
                    'naming_contexts': ['DC=mydomain,DC=com'],  # Default fallback
                    'default_naming_context': 'DC=mydomain,DC=com'
                }
        except Exception as e:
            print(f"Error listing base DNs: {e}")
            return {
                'naming_contexts': [],
                'default_naming_context': None
            }
    
    def get_user_accounts(self, base_dn):
        """Retrieve user accounts from Active Directory"""
        if not self.conn:
            raise ConnectionError("Not connected to AD server. Call connect() first.")
        
        # First, try to list available base DNs
        base_dns_info = self.list_base_dns()
        print(f"Available naming contexts: {base_dns_info['naming_contexts']}")
        print(f"Default naming context: {base_dns_info['default_naming_context']}")
        
        # If no base_dn provided and we have a default, use it
        if not base_dn and base_dns_info['default_naming_context']:
            base_dn = base_dns_info['default_naming_context']
            print(f"Using default naming context as base DN: {base_dn}")
        
        # LDAP filter for user accounts - make it more inclusive
        ldap_filter = '(objectClass=user)'
        
        # Attributes to retrieve
        attrs = [
            'sAMAccountName',  # username
            'cn',              # common name
            'description',
            'lastLogon',
            'logonCount',
            'accountExpires',
            'whenCreated',
            'userAccountControl',
            'objectClass',
            'objectCategory'
        ]
        
        try:
            print(f"Searching for users with base DN: {base_dn}")
            print(f"Using filter: {ldap_filter}")
            
            self.conn.search(
                search_base=base_dn,
                search_filter=ldap_filter,
                search_scope=SUBTREE,
                attributes=attrs
            )
            
            print(f"Search returned {len(self.conn.entries)} entries")
            
            # Process results
            users = []
            for entry in self.conn.entries:
                user = {}
                
                # Extract username
                if hasattr(entry, 'sAMAccountName'):
                    user['username'] = entry.sAMAccountName.value
                else:
                    continue  # Skip entries without username
                
                # Extract description
                if hasattr(entry, 'description'):
                    user['description'] = entry.description.value
                else:
                    user['description'] = ''
                
                # Extract last login time
                if hasattr(entry, 'lastLogon'):
                    # Convert Windows filetime to datetime
                    filetime = entry.lastLogon.value
                    if filetime and filetime > 0:
                        # Windows filetime is 100-nanosecond intervals since Jan 1, 1601
                        delta = timedelta(microseconds=filetime // 10)
                        epoch = datetime(1601, 1, 1)
                        last_logon = epoch + delta
                        user['last_login'] = last_logon.strftime('%Y-%m-%d')
                    else:
                        user['last_login'] = 'Never'
                else:
                    user['last_login'] = 'Unknown'
                
                # Extract login count
                if hasattr(entry, 'logonCount'):
                    user['login_count'] = entry.logonCount.value
                else:
                    user['login_count'] = 0
                
                # Extract account expiry
                if hasattr(entry, 'accountExpires'):
                    expiry = entry.accountExpires.value
                    if expiry and expiry > 0 and expiry < 9223372036854775807:  # Max value means no expiry
                        delta = timedelta(microseconds=expiry // 10)
                        epoch = datetime(1601, 1, 1)
                        expiry_date = epoch + delta
                        user['expiry_date'] = expiry_date.strftime('%Y-%m-%d')
                        user['has_expiry_date'] = True
                    else:
                        user['expiry_date'] = None
                        user['has_expiry_date'] = False
                else:
                    user['expiry_date'] = None
                    user['has_expiry_date'] = False
                
                # Extract account creation date
                if hasattr(entry, 'whenCreated'):
                    created_date = entry.whenCreated.value
                    if isinstance(created_date, datetime):
                        user['created_date'] = created_date.strftime('%Y-%m-%d')
                        
                        # Calculate account age in days
                        user['account_age'] = (datetime.now() - created_date).days
                    else:
                        user['created_date'] = 'Unknown'
                        user['account_age'] = 30  # Default value
                else:
                    user['created_date'] = 'Unknown'
                    user['account_age'] = 30  # Default value
                
                users.append(user)
            
            print(f"Processed {len(users)} user accounts")
            
            # If no users found, try with a more inclusive filter
            if not users:
                print("No users found with standard filter. Trying with a more inclusive filter...")
                ldap_filter = '(objectClass=*)'
                
                self.conn.search(
                    search_base=base_dn,
                    search_filter=ldap_filter,
                    search_scope=SUBTREE,
                    attributes=['objectClass'],
                    size_limit=10  # Just get a few to see what's there
                )
                
                print(f"Found {len(self.conn.entries)} objects with inclusive filter")
                for entry in self.conn.entries[:5]:  # Show first 5
                    print(f"Object: {entry.entry_dn}, Classes: {entry.objectClass.values if hasattr(entry, 'objectClass') else 'Unknown'}")
            
            return pd.DataFrame(users)
        
        except Exception as e:
            print(f"LDAP search failed: {e}")
            print(traceback.format_exc())
            return pd.DataFrame()
    
    def create_sample_data(self, count=100):
        """Create sample user data for testing purposes"""
        print(f"Creating {count} sample user accounts for testing")
        
        users = []
        
        # Define patterns for permanent and temporary accounts
        permanent_patterns = ['pf', 'it', 'mk', 'hr', 'fin']
        temp_patterns = ['test', 'temp', 'audit', 'tmp']
        
        # Define descriptions
        perm_descriptions = ['Regular employee', 'IT staff', 'Finance department', 'HR department', '']
        temp_descriptions = ['Temporary access', 'For testing', 'Audit account', 'Training account', '']
        
        now = datetime.now()
        
        for i in range(count):
            user = {}
            
            # Determine if this is a permanent or temporary account (70% permanent, 30% temporary)
            is_permanent = random.random() < 0.7
            
            if is_permanent:
                # Generate permanent username
                prefix = random.choice(permanent_patterns)
                number = random.randint(10000000, 99999999)
                user['username'] = f"{prefix}{number}"
                user['description'] = random.choice(perm_descriptions)
                
                # Permanent accounts have no expiry
                user['expiry_date'] = None
                user['has_expiry_date'] = False
                
                # Permanent accounts have higher login counts
                user['login_count'] = random.randint(10, 500)
                
                # Last login between 0 and 60 days ago
                days_ago = random.randint(0, 60)
                last_login = now - timedelta(days=days_ago)
                user['last_login'] = last_login.strftime('%Y-%m-%d')
                
                # Account created between 1 and 3 years ago
                days_old = random.randint(365, 365 * 3)
                created_date = now - timedelta(days=days_old)
                user['created_date'] = created_date.strftime('%Y-%m-%d')
                user['account_age'] = days_old
            else:
                # Generate temporary username
                if random.random() < 0.5:
                    # Pattern-based temporary username
                    prefix = random.choice(temp_patterns)
                    suffix = random.randint(1000, 9999)
                    user['username'] = f"{prefix}{suffix}"
                else:
                    # Random temporary username
                    if random.random() < 0.33:
                        # Short name
                        user['username'] = ''.join(random.choice('abcdefghijklmnopqrstuvwxyz') for _ in range(3))
                    elif random.random() < 0.66:
                        # Numeric name
                        user['username'] = str(random.randint(100000000000, 999999999999))
                    else:
                        # Random string
                        user['username'] = ''.join(random.choice('abcdefghijklmnopqrstuvwxyz0123456789') for _ in range(8))
                
                user['description'] = random.choice(temp_descriptions)
                
                # 50% chance of having an expiry date
                if random.random() < 0.5:
                    days_until_expiry = random.randint(1, 90)
                    expiry_date = now + timedelta(days=days_until_expiry)
                    user['expiry_date'] = expiry_date.strftime('%Y-%m-%d')
                    user['has_expiry_date'] = True
                else:
                    user['expiry_date'] = None
                    user['has_expiry_date'] = False
                
                # Temporary accounts have lower login counts
                user['login_count'] = random.randint(0, 10)
                
                # Determine if this is an inactive account (40% chance)
                is_inactive = random.random() < 0.4
                
                if is_inactive:
                    # Inactive accounts have old last login dates
                    days_ago = random.randint(90, 365)
                    last_login = now - timedelta(days=days_ago)
                    user['last_login'] = last_login.strftime('%Y-%m-%d')
                else:
                    # Active accounts have recent last login dates
                    days_ago = random.randint(0, 30)
                    last_login = now - timedelta(days=days_ago)
                    user['last_login'] = last_login.strftime('%Y-%m-%d')
                
                # Account created between 1 and 180 days ago
                days_old = random.randint(1, 180)
                created_date = now - timedelta(days=days_old)
                user['created_date'] = created_date.strftime('%Y-%m-%d')
                user['account_age'] = days_old
            
            users.append(user)
        
        return pd.DataFrame(users)
    
    def disable_account(self, username, base_dn):
        """Disable a user account in Active Directory"""
        if not self.conn:
            raise ConnectionError("Not connected to AD server. Call connect() first.")
        
        try:
            # Find the user DN
            ldap_filter = f'(&(objectClass=user)(sAMAccountName={username}))'
            self.conn.search(
                search_base=base_dn,
                search_filter=ldap_filter,
                search_scope=SUBTREE,
                attributes=['distinguishedName']
            )
            
            if not self.conn.entries:
                return False, f"User {username} not found"
            
            user_dn = self.conn.entries[0].entry_dn
            
            # Set the userAccountControl attribute to disable the account
            # 0x0002 is the flag for disabled accounts
            # First, get the current value
            self.conn.search(
                search_base=user_dn,
                search_filter='(objectClass=*)',
                search_scope=SUBTREE,
                attributes=['userAccountControl']
            )
            
            if not self.conn.entries:
                return False, f"Failed to retrieve userAccountControl for {username}"
            
            current_uac = self.conn.entries[0].userAccountControl.value
            
            # Set the disabled bit (0x0002)
            new_uac = current_uac | 2
            
            # Update the attribute
            result = self.conn.modify(
                user_dn,
                {'userAccountControl': [(self.conn.MODIFY_REPLACE, [new_uac])]}
            )
            
            if result:
                return True, f"User {username} disabled successfully"
            else:
                return False, f"Failed to disable user {username}: {self.conn.result}"
        
        except Exception as e:
            return False, f"Failed to disable user {username}: {e}"
    
    def delete_account(self, username, base_dn):
        """Delete a user account from Active Directory"""
        if not self.conn:
            raise ConnectionError("Not connected to AD server. Call connect() first.")
        
        try:
            # Find the user DN
            ldap_filter = f'(&(objectClass=user)(sAMAccountName={username}))'
            self.conn.search(
                search_base=base_dn,
                search_filter=ldap_filter,
                search_scope=SUBTREE,
                attributes=['distinguishedName']
            )
            
            if not self.conn.entries:
                return False, f"User {username} not found"
            
            user_dn = self.conn.entries[0].entry_dn
            
            # Delete the user
            result = self.conn.delete(user_dn)
            
            if result:
                return True, f"User {username} deleted successfully"
            else:
                return False, f"Failed to delete user {username}: {self.conn.result}"
        
        except Exception as e:
            return False, f"Failed to delete user {username}: {e}"