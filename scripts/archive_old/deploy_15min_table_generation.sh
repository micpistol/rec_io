#!/bin/bash

# 15-MINUTE MASTER PROBABILITY TABLE GENERATION DEPLOYMENT
# 
# This script deploys the 15-minute master probability table generator to Google Cloud
# for cost-effective generation of the lookup table.
#
# Estimated cost: ~$38
# Estimated time: 2-3 days
# Total combinations: 110,000,000

set -e

# Configuration
PROJECT_ID="your-google-cloud-project-id"  # UPDATE THIS
INSTANCE_NAME="master-prob-table-15min"
MACHINE_TYPE="n2-standard-32"  # 32 vCPUs, 128GB RAM
ZONE="us-central1-a"
DISK_SIZE="50GB"
SCRIPT_PATH="backend/util/master_probability_table_generator_15min.py"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if gcloud is installed
check_gcloud() {
    if ! command -v gcloud &> /dev/null; then
        log_error "gcloud CLI is not installed. Please install it first:"
        log_error "https://cloud.google.com/sdk/docs/install"
        exit 1
    fi
    
    log_success "gcloud CLI found"
}

# Check if user is authenticated
check_auth() {
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
        log_error "Not authenticated with gcloud. Please run:"
        log_error "gcloud auth login"
        exit 1
    fi
    
    log_success "gcloud authentication verified"
}

# Set up the project
setup_project() {
    log_info "Setting up Google Cloud project..."
    
    # Set the project
    gcloud config set project $PROJECT_ID
    
    # Enable required APIs
    gcloud services enable compute.googleapis.com
    gcloud services enable cloudresourcemanager.googleapis.com
    
    log_success "Project setup complete"
}

# Create the VM instance
create_instance() {
    log_info "Creating VM instance for table generation..."
    
    # Create the instance
    gcloud compute instances create $INSTANCE_NAME \
        --zone=$ZONE \
        --machine-type=$MACHINE_TYPE \
        --image-family=ubuntu-2004-lts \
        --image-project=ubuntu-os-cloud \
        --boot-disk-size=$DISK_SIZE \
        --boot-disk-type=pd-ssd \
        --maintenance-policy=TERMINATE \
        --restart-on-failure \
        --scopes=cloud-platform \
        --metadata=startup-script="#!/bin/bash
# Install required packages
apt-get update
apt-get install -y python3 python3-pip python3-venv postgresql-client git

# Create working directory
mkdir -p /opt/master-prob-table
cd /opt/master-prob-table

# Clone the repository (you'll need to update this URL)
git clone https://github.com/your-username/rec_io_20.git .

# Set up Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set up environment variables
echo 'export POSTGRES_HOST=your-db-host' >> ~/.bashrc
echo 'export POSTGRES_DB=rec_io_db' >> ~/.bashrc
echo 'export POSTGRES_USER=rec_io_user' >> ~/.bashrc
echo 'export POSTGRES_PASSWORD=your-db-password' >> ~/.bashrc

# Start the generation process
cd /opt/master-prob-table
source venv/bin/activate
nohup python3 $SCRIPT_PATH --batch-size 10000 > generation.log 2>&1 &
echo \$! > generation.pid
"
    
    log_success "VM instance created: $INSTANCE_NAME"
}

# Wait for instance to be ready
wait_for_instance() {
    log_info "Waiting for instance to be ready..."
    
    # Wait for instance to be running
    while ! gcloud compute instances describe $INSTANCE_NAME --zone=$ZONE --format="value(status)" | grep -q "RUNNING"; do
        sleep 10
    done
    
    # Wait a bit more for startup script to complete
    sleep 60
    
    log_success "Instance is ready"
}

# Get instance IP
get_instance_ip() {
    INSTANCE_IP=$(gcloud compute instances describe $INSTANCE_NAME --zone=$ZONE --format="value(networkInterfaces[0].accessConfigs[0].natIP)")
    echo $INSTANCE_IP
}

# Monitor generation progress
monitor_progress() {
    log_info "Monitoring generation progress..."
    
    INSTANCE_IP=$(get_instance_ip)
    
    while true; do
        # Check if generation is still running
        PID=$(gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --command="cat /opt/master-prob-table/generation.pid 2>/dev/null || echo 'NOT_RUNNING'")
        
        if [ "$PID" = "NOT_RUNNING" ]; then
            log_warning "Generation process not found. Checking logs..."
            gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --command="tail -50 /opt/master-prob-table/generation.log"
            break
        fi
        
        # Check if process is still running
        if ! gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --command="ps -p $PID > /dev/null 2>&1"; then
            log_warning "Generation process stopped. Checking logs..."
            gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --command="tail -50 /opt/master-prob-table/generation.log"
            break
        fi
        
        # Show progress
        log_info "Generation is running (PID: $PID). Checking progress..."
        gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --command="tail -10 /opt/master-prob-table/generation.log | grep -E '(Processed|ETA|Rate)' || echo 'No progress info found'"
        
        # Wait before next check
        sleep 300  # Check every 5 minutes
    done
}

# Download results
download_results() {
    log_info "Downloading generation results..."
    
    # Create local directory for results
    mkdir -p ./generation_results
    
    # Download logs and results
    gcloud compute scp $INSTANCE_NAME:/opt/master-prob-table/generation.log ./generation_results/ --zone=$ZONE
    gcloud compute scp $INSTANCE_NAME:/opt/master-prob-table/master_probability_table_15min_generator.log ./generation_results/ --zone=$ZONE
    
    log_success "Results downloaded to ./generation_results/"
}

# Clean up instance
cleanup_instance() {
    log_info "Cleaning up VM instance..."
    
    read -p "Do you want to delete the VM instance? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        gcloud compute instances delete $INSTANCE_NAME --zone=$ZONE --quiet
        log_success "VM instance deleted"
    else
        log_info "VM instance preserved. You can access it at: $(get_instance_ip)"
    fi
}

# Show cost estimate
show_cost_estimate() {
    log_info "Cost Estimate:"
    log_info "  Instance: $MACHINE_TYPE"
    log_info "  Estimated runtime: 2-3 days"
    log_info "  Cost per hour: ~$0.79"
    log_info "  Total estimated cost: ~$38"
    log_info ""
    log_info "To monitor costs:"
    log_info "  https://console.cloud.google.com/billing"
}

# Main execution
main() {
    log_info "Starting 15-minute master probability table generation deployment"
    log_info "Project: $PROJECT_ID"
    log_info "Instance: $INSTANCE_NAME"
    log_info "Machine type: $MACHINE_TYPE"
    
    # Pre-flight checks
    check_gcloud
    check_auth
    
    # Show cost estimate
    show_cost_estimate
    
    # Confirm before proceeding
    read -p "Continue with deployment? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Deployment cancelled"
        exit 0
    fi
    
    # Execute deployment steps
    setup_project
    create_instance
    wait_for_instance
    
    log_success "Deployment complete!"
    log_info "Instance IP: $(get_instance_ip)"
    log_info "SSH command: gcloud compute ssh $INSTANCE_NAME --zone=$ZONE"
    log_info "Monitor logs: gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --command='tail -f /opt/master-prob-table/generation.log'"
    
    # Ask if user wants to monitor progress
    read -p "Monitor generation progress? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        monitor_progress
        download_results
        cleanup_instance
    else
        log_info "To monitor manually:"
        log_info "  gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --command='tail -f /opt/master-prob-table/generation.log'"
        log_info "To download results later:"
        log_info "  gcloud compute scp $INSTANCE_NAME:/opt/master-prob-table/generation.log ./ --zone=$ZONE"
    fi
}

# Handle script arguments
case "${1:-}" in
    "monitor")
        monitor_progress
        ;;
    "download")
        download_results
        ;;
    "cleanup")
        cleanup_instance
        ;;
    "ip")
        get_instance_ip
        ;;
    *)
        main
        ;;
esac
