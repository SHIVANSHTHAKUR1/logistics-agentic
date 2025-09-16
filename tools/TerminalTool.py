import subprocess
from langchain_core.tools import tool

@tool
def run_windows_command(command: str) -> str:
    """Execute a Windows command and return the output.
    
    This tool is optimized for Google Gemini models and provides robust error handling.
    
    Args:
        command (str): The Windows command to execute. Can include shell commands, 
                      batch files, PowerShell commands, or any executable available 
                      in the system PATH. Examples: 'dir', 'echo hello', 'python script.py'
    
    Returns:
        str: The command output (stdout) if successful, or error message (stderr) 
             if the command fails. Returns "Error: <exception_message>" if an 
             exception occurs during execution.
    """
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        
        # Enhanced output handling for Gemini
        if result.returncode == 0:
            output = result.stdout.strip() if result.stdout else "Command executed successfully (no output)"
            return f"✅ Success: {output}"
        else:
            error = result.stderr.strip() if result.stderr else f"Command failed with exit code {result.returncode}"
            return f"❌ Error: {error}"
    except subprocess.TimeoutExpired:
        return "❌ Error: Command timed out after 30 seconds"
    except Exception as e:
        return f"❌ Error: {str(e)}"