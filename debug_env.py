#!/usr/bin/env python3
"""
Debug script to find issues in .env file
Run this to identify problems with your .env file formatting
"""

def debug_env_file(filepath='.env'):
    """
    Read and validate .env file line by line
    """
    print(f"🔍 Debugging {filepath}...\n")
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"❌ Error: {filepath} file not found!")
        return
    
    issues_found = False
    
    for line_num, line in enumerate(lines, start=1):
        # Skip empty lines and comments
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        
        # Check for common issues
        problems = []
        
        # Issue 1: No = sign
        if '=' not in line:
            problems.append("Missing '=' sign")
        
        # Issue 2: Spaces around = sign (common but not always wrong)
        if ' = ' in line:
            problems.append("Spaces around '=' (remove them)")
        
        # Issue 3: Multiline value without quotes
        if line.count('"') == 1 or line.count("'") == 1:
            problems.append("Unclosed quote")
        
        # Issue 4: Special characters without quotes
        if '=' in line:
            key, _, value = line.partition('=')
            value = value.strip()
            special_chars = ['$', '!', '@', '#', '%', '^', '&', '*', '(', ')', '{', '}', '[', ']', '|', '\\', ';', ':', '<', '>', ',', '?']
            if any(char in value for char in special_chars) and not (value.startswith('"') or value.startswith("'")):
                problems.append("Special characters without quotes")
        
        # Issue 5: Tab characters
        if '\t' in line:
            problems.append("Contains tab character (use spaces)")
        
        # Issue 6: Trailing spaces after value
        if '=' in line and line.rstrip() != line.rstrip('\n'):
            problems.append("Trailing spaces after value")
        
        # Report line
        if problems:
            issues_found = True
            print(f"⚠️  Line {line_num}: {problems}")
            print(f"   Content: {repr(line)}")
            print(f"   Visible: {line.rstrip()}")
            print()
        else:
            # Show valid lines
            if '=' in stripped:
                key = stripped.split('=')[0]
                print(f"✅ Line {line_num}: {key}=***")
    
    if not issues_found:
        print("✨ No obvious issues found in .env file!")
        print("   If you're still getting errors, check for:")
        print("   - Hidden characters (BOM, zero-width spaces)")
        print("   - File encoding (should be UTF-8)")
        print("   - Line endings (should be LF, not CRLF)")
    else:
        print("\n" + "="*60)
        print("📋 Common .env file rules:")
        print("="*60)
        print("1. Format: KEY=value (no spaces around =)")
        print("2. Comments start with #")
        print("3. Use quotes for values with spaces or special chars:")
        print("   EMAIL_PASSWORD=\"my pass@123\"")
        print("4. No spaces at end of lines")
        print("5. Use UTF-8 encoding")
        print("6. Blank lines are OK")
        print("\n💡 To fix: Edit your .env file and correct the issues above")

if __name__ == '__main__':
    import sys
    filepath = sys.argv[1] if len(sys.argv) > 1 else '.env'
    debug_env_file(filepath)
    
    print("\n" + "="*60)
    print("🔧 Quick Fix Examples:")
    print("="*60)
    print("\n❌ WRONG:")
    print("SECRET_KEY = my-secret-key")
    print("EMAIL_PASSWORD=mypass@123")
    print("ADMIN_PASSWORD='password'  ")
    print("\n✅ CORRECT:")
    print("SECRET_KEY=my-secret-key")
    print('EMAIL_PASSWORD="mypass@123"')
    print("ADMIN_PASSWORD=password")