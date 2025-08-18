#!/usr/bin/env python3
"""
Kalshi Credentials Generator
Creates a complete set of Kalshi credential files for both prod and demo environments.
"""

import os
import sys
import argparse
from pathlib import Path


def get_project_root():
    """Get the project root directory."""
    return Path(__file__).parent.parent


def create_credentials_directory(env):
    """Create the credentials directory for the specified environment."""
    from backend.util.paths import get_kalshi_credentials_dir
    base_path = Path(get_kalshi_credentials_dir()) / env
    base_path.mkdir(parents=True, exist_ok=True)
    return base_path


def write_auth_file(credentials_dir, email, api_key):
    """Write the kalshi-auth.txt file."""
    auth_file = credentials_dir / "kalshi-auth.txt"
    content = f"email:{email}\nkey:{api_key}\n"
    
    with open(auth_file, 'w') as f:
        f.write(content)
    
    print(f"✅ Created: {auth_file}")
    return auth_file


def write_pem_file(credentials_dir, pem_content):
    """Write the kalshi-auth.pem file."""
    pem_file = credentials_dir / "kalshi-auth.pem"
    
    with open(pem_file, 'w') as f:
        f.write(pem_content)
    
    # Set proper permissions for private key
    os.chmod(pem_file, 0o600)
    print(f"✅ Created: {pem_file}")
    return pem_file


def write_env_file(credentials_dir, env_content=None):
    """Write the kalshi.env file (optional)."""
    env_file = credentials_dir / "kalshi.env"
    
    if env_content:
        with open(env_file, 'w') as f:
            f.write(env_content)
        print(f"✅ Created: {env_file}")
    else:
        # Create a basic template if no content provided
        template = """# Kalshi Environment Variables
# Add any additional environment variables here
# Example:
# KALSHI_API_URL=https://api.elections.kalshi.com
# KALSHI_SANDBOX_URL=https://demo-api.elections.kalshi.com
"""
        with open(env_file, 'w') as f:
            f.write(template)
        print(f"✅ Created template: {env_file}")
    
    return env_file


def prompt_for_input(prompt_text, default=None):
    """Prompt user for input with optional default value."""
    if default:
        user_input = input(f"{prompt_text} [{default}]: ").strip()
        return user_input if user_input else default
    else:
        return input(f"{prompt_text}: ").strip()


def get_pem_template():
    """Return a PEM file template."""
    return """-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC...
[Replace with your actual private key content]
-----END PRIVATE KEY-----"""


def get_env_template(env):
    """Return environment-specific ENV file template."""
    if env == "prod":
        return """# Production Environment Variables
KALSHI_API_URL=https://api.elections.kalshi.com
KALSHI_ENVIRONMENT=production
"""
    else:
        return """# Demo Environment Variables  
KALSHI_API_URL=https://demo-api.elections.kalshi.com
KALSHI_ENVIRONMENT=demo
"""


def create_credentials_for_env(env, email, api_key, pem_content=None, env_content=None):
    """Create all credential files for a specific environment."""
    print(f"\n🔧 Creating credentials for {env.upper()} environment...")
    
    # Create directory
    credentials_dir = create_credentials_directory(env)
    
    # Write auth file
    write_auth_file(credentials_dir, email, api_key)
    
    # Write PEM file
    if pem_content:
        write_pem_file(credentials_dir, pem_content)
    else:
        print(f"⚠️  No PEM content provided for {env} - skipping kalshi-auth.pem")
    
    # Write ENV file
    if env_content:
        write_env_file(credentials_dir, env_content)
    else:
        write_env_file(credentials_dir, get_env_template(env))
    
    print(f"✅ Completed {env.upper()} credentials setup")


def main():
    parser = argparse.ArgumentParser(description="Generate Kalshi credentials files")
    parser.add_argument("--email", help="Kalshi account email")
    parser.add_argument("--api-key", help="Kalshi API key")
    parser.add_argument("--pem-file", help="Path to PEM file to copy")
    parser.add_argument("--env-file", help="Path to ENV file to copy")
    parser.add_argument("--environments", choices=["prod", "demo", "both"], default="both",
                       help="Which environments to create (default: both)")
    parser.add_argument("--interactive", action="store_true", 
                       help="Force interactive mode even if arguments provided")
    
    args = parser.parse_args()
    
    print("🔐 Kalshi Credentials Generator")
    print("=" * 40)
    
    # Determine if we should use interactive mode
    use_interactive = args.interactive or not (args.email and args.api_key)
    
    if use_interactive:
        print("\n📝 Interactive Mode - Please provide the following information:")
        
        # Get email
        email = args.email or prompt_for_input("Enter Kalshi account email")
        if not email:
            print("❌ Email is required")
            sys.exit(1)
        
        # Get API key
        api_key = args.api_key or prompt_for_input("Enter Kalshi API key")
        if not api_key:
            print("❌ API key is required")
            sys.exit(1)
        
        # Get PEM content
        pem_content = None
        if args.pem_file:
            try:
                with open(args.pem_file, 'r') as f:
                    pem_content = f.read()
                print(f"✅ Loaded PEM from: {args.pem_file}")
            except FileNotFoundError:
                print(f"❌ PEM file not found: {args.pem_file}")
                sys.exit(1)
        else:
            use_pem = prompt_for_input("Do you have a PEM file? (y/n)", "n").lower()
            if use_pem == 'y':
                pem_path = prompt_for_input("Enter path to PEM file")
                try:
                    with open(pem_path, 'r') as f:
                        pem_content = f.read()
                    print(f"✅ Loaded PEM from: {pem_path}")
                except FileNotFoundError:
                    print(f"❌ PEM file not found: {pem_path}")
                    print("⚠️  Continuing without PEM file")
        
        # Get ENV content
        env_content = None
        if args.env_file:
            try:
                with open(args.env_file, 'r') as f:
                    env_content = f.read()
                print(f"✅ Loaded ENV from: {args.env_file}")
            except FileNotFoundError:
                print(f"❌ ENV file not found: {args.env_file}")
        else:
            use_env = prompt_for_input("Do you have custom ENV variables? (y/n)", "n").lower()
            if use_env == 'y':
                print("Enter ENV content (press Enter twice to finish):")
                lines = []
                while True:
                    line = input()
                    if line == "" and lines and lines[-1] == "":
                        break
                    lines.append(line)
                env_content = "\n".join(lines[:-1])  # Remove the last empty line
        
        # Get environments
        if args.environments == "both":
            envs = ["prod", "demo"]
        else:
            envs = [args.environments]
        
        # Confirm before creating
        print(f"\n📋 Summary:")
        print(f"  Email: {email}")
        print(f"  API Key: {api_key[:8]}...{api_key[-4:]}")
        print(f"  PEM: {'Yes' if pem_content else 'No'}")
        print(f"  ENV: {'Yes' if env_content else 'No'}")
        print(f"  Environments: {', '.join(envs)}")
        
        confirm = prompt_for_input("Proceed with creating credentials? (y/n)", "y").lower()
        if confirm != 'y':
            print("❌ Cancelled")
            sys.exit(0)
        
    else:
        # Non-interactive mode
        email = args.email
        api_key = args.api_key
        
        # Load PEM content
        pem_content = None
        if args.pem_file:
            try:
                with open(args.pem_file, 'r') as f:
                    pem_content = f.read()
            except FileNotFoundError:
                print(f"❌ PEM file not found: {args.pem_file}")
                sys.exit(1)
        
        # Load ENV content
        env_content = None
        if args.env_file:
            try:
                with open(args.env_file, 'r') as f:
                    env_content = f.read()
            except FileNotFoundError:
                print(f"❌ ENV file not found: {args.env_file}")
                sys.exit(1)
        
        # Determine environments
        if args.environments == "both":
            envs = ["prod", "demo"]
        else:
            envs = [args.environments]
    
    # Create credentials for each environment
    for env in envs:
        create_credentials_for_env(env, email, api_key, pem_content, env_content)
    
    print(f"\n✅ Credentials generation completed!")
    from backend.util.paths import get_kalshi_credentials_dir
    print(f"📁 Files created in: {get_kalshi_credentials_dir()}/")
    print("\n🔒 SECURITY: Credentials stored ONLY in user-based location")
    print("🔒 Security Note: Ensure PEM files have restricted permissions (600)")


if __name__ == "__main__":
    main() 