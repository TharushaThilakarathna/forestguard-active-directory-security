from flask import Flask, request, jsonify, render_template, session
from flask_cors import CORS
import pandas as pd
import json
import os
from datetime import datetime, timedelta
import traceback
import re

# Import our modules
from ad_connector import ADConnector
from isolation_forest_model import IsolationForestModel
from random_forest_model import RandomForestModel

app = Flask(__name__)
app.secret_key = os.urandom(24)  # For session management
CORS(app)  # Enable CORS for all routes

# Initialize models
isolation_forest = IsolationForestModel()
random_forest = RandomForestModel()

# Try to load pre-trained models if they exist
try:
    isolation_forest.load_model()
    print("Loaded Isolation Forest model")
except:
    print("No pre-trained Isolation Forest model found")
    # Train the model using the provided CSV
    if os.path.exists('isolation_forest_sample.csv'):
        print("Training Isolation Forest model from CSV...")
        isolation_forest.train_from_csv('isolation_forest_sample.csv')
        print("Isolation Forest model trained")
    else:
        print("CSV file not found. Please run train_models.py first")

try:
    random_forest.load_model()
    print("Loaded Random Forest model")
except:
    print("No pre-trained Random Forest model found")
    # Train the model using the provided CSV
    if os.path.exists('random_forest_sample.csv'):
        print("Training Random Forest model from CSV...")
        random_forest.train_from_csv('random_forest_sample.csv')
        print("Random Forest model trained")
    else:
        print("CSV file not found. Please run train_models.py first")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/results')
def results():
    if 'analysis_results' not in session:
        return render_template('index.html', error="Please analyze AD accounts first")
    return render_template('results.html')

@app.route('/api/test-connection', methods=['POST'])
def test_connection():
    """Endpoint to test AD server connection without performing full analysis"""
    try:
        data = request.json
        if not data:
            return jsonify({
                'success': False,
                'error': 'Invalid request data',
                'details': {
                    'network_connectivity': False,
                    'authentication': False
                }
            }), 400
            
        server = data.get('server')
        username = data.get('username')
        password = data.get('password')
        
        if not server or not username or not password:
            return jsonify({
                'success': False,
                'error': 'Missing required fields (server, username, or password)',
                'details': {
                    'network_connectivity': False,
                    'authentication': False
                }
            }), 400
        
        # Print connection details for debugging
        print(f"Testing connection to AD server: {server}")
        print(f"With username: {username}")
        
        # Test network connectivity first
        connector = ADConnector(server, username, password)
        network_ok = connector.test_network_connection()
        
        if not network_ok:
            return jsonify({
                'success': False,
                'error': 'Network connectivity test failed. Cannot reach the server.',
                'details': {
                    'network_connectivity': False,
                    'authentication': False
                }
            }), 400
        
        # Try to connect to AD
        connection_ok = connector.connect()
        
        if connection_ok:
            # Get available base DNs
            base_dns_info = connector.list_base_dns()
            available_base_dns = base_dns_info['naming_contexts']
            default_base_dn = base_dns_info['default_naming_context']
            
            return jsonify({
                'success': True,
                'message': 'Successfully connected to AD server',
                'details': {
                    'network_connectivity': True,
                    'authentication': True,
                    'available_base_dns': available_base_dns,
                    'default_base_dn': default_base_dn
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to authenticate with AD server. Check credentials.',
                'details': {
                    'network_connectivity': True,
                    'authentication': False
                }
            }), 401
    except Exception as e:
        print(f"Error in test_connection: {str(e)}")
        print(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': f'An unexpected error occurred: {str(e)}',
            'details': {
                'network_connectivity': False,
                'authentication': False
            }
        }), 500
    finally:
        # Use close() instead of disconnect()
        if 'connector' in locals() and connector.conn:
            connector.close()

@app.route('/api/analyze', methods=['POST'])
def analyze():
    data = request.json
    server = data.get('server')
    username = data.get('username')
    password = data.get('password')
    base_dn = data.get('base_dn', '')  # Make base_dn optional
    debug_mode = data.get('debug', False)  # Debug mode flag
    
    # Print connection details for debugging (remove in production)
    print(f"Connecting to AD server: {server}")
    print(f"With username: {username}")
    print(f"Base DN: {base_dn}")
    print(f"Debug mode: {debug_mode}")
    
    # Store debug logs if debug mode is enabled
    debug_logs = []
    
    def log_debug(message):
        print(message)
        if debug_mode:
            debug_logs.append(message)
    
    log_debug("Starting analysis process...")
    
    # Connect to AD
    connector = ADConnector(server, username, password)
    if not connector.connect():
        return jsonify({
            'success': False, 
            'error': 'Failed to connect to AD server. Please check your credentials and server address. See server logs for details.'
        }), 401
    
    try:
        # Get available base DNs
        base_dns_info = connector.list_base_dns()
        available_base_dns = base_dns_info['naming_contexts']
        default_base_dn = base_dns_info['default_naming_context']
        
        print(f"Available base DNs: {available_base_dns}")
        print(f"Default base DN: {default_base_dn}")
        
        # If no base_dn provided, use default
        if not base_dn and default_base_dn:
            base_dn = default_base_dn
            print(f"Using default base DN: {base_dn}")
        
        # Get user accounts from AD
        df = connector.get_user_accounts(base_dn)
        
        if df.empty:
            log_debug("No user accounts found with standard search")
            
            # Check if we should use sample data for testing
            if debug_mode:
                log_debug("Debug mode enabled - creating sample data for testing")
                df = connector.create_sample_data(count=100)
                log_debug(f"Created {len(df)} sample user accounts")
            else:
                # If no users found, try to provide helpful information
                return jsonify({
                    'success': False, 
                    'error': f'No user accounts found. Please check your Base DN setting. Available Base DNs: {", ".join(available_base_dns) if available_base_dns else "None found"}',
                    'details': {
                        'available_base_dns': available_base_dns,
                        'default_base_dn': default_base_dn,
                        'suggestions': [
                            "Try a different Base DN format (e.g., DC=domain,DC=com)",
                            "Check if the administrator account has sufficient permissions",
                            "Try a different username format (domain\\username, username@domain.com)",
                            "Verify that there are user accounts in the directory",
                            "Enable Debug Mode to use sample data for testing"
                        ],
                        'debug_logs': debug_logs if debug_mode else []
                    }
                }), 404
        
        print(f"Found {len(df)} user accounts")
        
        # If we have no trained models, create simple ones with the current data
        if isolation_forest.model is None:
            print("Training Isolation Forest model with current data...")
            isolation_forest.train(df)
        
        # Predict temporary accounts using Isolation Forest
        try:
            is_temporary = isolation_forest.predict(df)
            df['is_temporary'] = is_temporary
            
            # For temporary accounts, predict inactive ones
            temp_accounts = df[df['is_temporary']]
            if not temp_accounts.empty:
                if random_forest.model is None:
                    print("Training Random Forest model with temporary accounts...")
                    random_forest.train(temp_accounts)
                
                is_inactive = random_forest.predict(temp_accounts)
                
                # Add inactive flag to the main dataframe
                df['is_inactive'] = False
                df.loc[df['is_temporary'], 'is_inactive'] = is_inactive
            else:
                # If no temporary accounts, mark all as not inactive
                df['is_inactive'] = False
        except Exception as e:
            print(f"Error in prediction: {str(e)}")
            print(traceback.format_exc())
            # If prediction fails, use simple heuristics
            print("Using simple heuristics for classification...")
            
            # Mark accounts as temporary based on username patterns
            df['is_temporary'] = df['username'].apply(
                lambda x: any(re.match(pattern, str(x)) for pattern in isolation_forest.temp_patterns)
            )
            
            # Mark accounts as inactive based on login count
            df['is_inactive'] = False
            if 'login_count' in df.columns:
                df.loc[df['is_temporary'], 'is_inactive'] = df.loc[df['is_temporary'], 'login_count'] < 5
        
        # Prepare results
        total_users = len(df)
        permanent_users = len(df[~df['is_temporary']])
        temporary_users = len(df[df['is_temporary']])
        inactive_temp_users = len(df[df['is_temporary'] & df['is_inactive']])
        
        # Convert dataframe to list of dictionaries for JSON serialization
        user_accounts = []
        for _, row in df.iterrows():
            account = {
                'id': row.name,
                'username': row['username'],
                'description': row.get('description', ''),
                'lastLogin': row.get('last_login', 'Unknown'),
                'loginCount': row.get('login_count', 0),
                'expiryDate': row.get('expiry_date'),
                'accountType': 'temporary' if row['is_temporary'] else 'permanent',
                'isActive': not row.get('is_inactive', False)
            }
            user_accounts.append(account)
        
        # Store results in session
        session['analysis_results'] = {
            'totalUsers': total_users,
            'permanentUsers': permanent_users,
            'temporaryUsers': temporary_users,
            'inactiveTempUsers': inactive_temp_users,
            'userAccounts': user_accounts
        }
        
        return jsonify({
            'success': True,
            'results': {
                'totalUsers': total_users,
                'permanentUsers': permanent_users,
                'temporaryUsers': temporary_users,
                'inactiveTempUsers': inactive_temp_users
            }
        })
    
    except Exception as e:
        print(f"Error during analysis: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'success': False, 'error': f'Error during analysis: {str(e)}'}), 500
    
    finally:
        # Use close() instead of disconnect()
        connector.close()

@app.route('/api/accounts', methods=['GET'])
def get_accounts():
    if 'analysis_results' not in session:
        return jsonify({'success': False, 'error': 'No analysis results found'}), 404
    
    # Filter to only return inactive temporary accounts
    inactive_accounts = [acc for acc in session['analysis_results']['userAccounts'] 
                         if acc['accountType'] == 'temporary' and not acc['isActive']]
    
    return jsonify({
        'success': True,
        'accounts': inactive_accounts,
        'summary': {
            'totalUsers': session['analysis_results']['totalUsers'],
            'permanentUsers': session['analysis_results']['permanentUsers'],
            'temporaryUsers': session['analysis_results']['temporaryUsers'],
            'inactiveTempUsers': session['analysis_results']['inactiveTempUsers']
        }
    })

@app.route('/api/disable', methods=['POST'])
def disable_accounts():
    data = request.json
    server = data.get('server')
    username = data.get('username')
    password = data.get('password')
    base_dn = data.get('base_dn', 'DC=example,DC=com')
    account_ids = data.get('accountIds', [])
    
    if not account_ids:
        return jsonify({'success': False, 'error': 'No accounts specified'}), 400
    
    # Connect to AD
    connector = ADConnector(server, username, password)
    if not connector.connect():
        return jsonify({'success': False, 'error': 'Failed to connect to AD server'}), 401
    
    try:
        results = []
        for account_id in account_ids:
            # Get username from session
            user_accounts = session['analysis_results']['userAccounts']
            username_to_disable = next((acc['username'] for acc in user_accounts if str(acc['id']) == str(account_id)), None)
            
            if username_to_disable:
                success, message = connector.disable_account(username_to_disable, base_dn)
                results.append({'id': account_id, 'username': username_to_disable, 'success': success, 'message': message})
            else:
                results.append({'id': account_id, 'success': False, 'message': 'Account not found'})
        
        return jsonify({'success': True, 'results': results})
    
    except Exception as e:
        print(f"Error disabling accounts: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500
    
    finally:
        # Use close() instead of disconnect()
        connector.close()

@app.route('/api/delete', methods=['POST'])
def delete_accounts():
    data = request.json
    server = data.get('server')
    username = data.get('username')
    password = data.get('password')
    base_dn = data.get('base_dn', 'DC=example,DC=com')
    account_ids = data.get('accountIds', [])
    
    if not account_ids:
        return jsonify({'success': False, 'error': 'No accounts specified'}), 400
    
    # Connect to AD
    connector = ADConnector(server, username, password)
    if not connector.connect():
        return jsonify({'success': False, 'error': 'Failed to connect to AD server'}), 401
    
    try:
        results = []
        for account_id in account_ids:
            # Get username from session
            user_accounts = session['analysis_results']['userAccounts']
            username_to_delete = next((acc['username'] for acc in user_accounts if str(acc['id']) == str(account_id)), None)
            
            if username_to_delete:
                success, message = connector.delete_account(username_to_delete, base_dn)
                results.append({'id': account_id, 'username': username_to_delete, 'success': success, 'message': message})
            else:
                results.append({'id': account_id, 'success': False, 'message': 'Account not found'})
        
        return jsonify({'success': True, 'results': results})
    
    except Exception as e:
        print(f"Error deleting accounts: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500
    
    finally:
        # Use close() instead of disconnect()
        connector.close()

if __name__ == '__main__':
    app.run(debug=True)