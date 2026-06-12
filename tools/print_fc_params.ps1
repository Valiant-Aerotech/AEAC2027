# Print Pixhawk parameters to set during first-time bringup (Phase B2 + B3)
$ErrorActionPreference = "Stop"

Write-Host "=== Vion FC parameters (set in Mission Planner) ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Pi companion TELEM port (replace x with your port number):" -ForegroundColor Yellow
Write-Host "  SERIALx_PROTOCOL = 2    # MAVLink2"
Write-Host "  SERIALx_BAUD     = 57   # 57600"
Write-Host "  (GCS radio must use a DIFFERENT SERIAL port)"
Write-Host ""
Write-Host "Holybro H-Flow (DroneCAN, downward):" -ForegroundColor Yellow
Write-Host "  FLOW_TYPE    = 6"
Write-Host "  RNGFND1_TYPE = 24"
Write-Host "  FLOW_POS_X/Y/Z and RNGFND1_POS_X/Y/Z = mount offset from CG"
Write-Host ""
Write-Host "Indoor flight:" -ForegroundColor Yellow
Write-Host "  GUIDED_NOGPS mode selectable in MP"
Write-Host "  Relax GPS geofence if needed for indoor profile"
Write-Host ""
Write-Host "Verify in MP:" -ForegroundColor Yellow
Write-Host "  DroneCAN status shows H-Flow"
Write-Host "  opt_qua reasonable on bench hover over venue-like floor"
Write-Host ""
Write-Host "Full notes: hardware\vion\mission-planner\002-pi-telem-params.md"
