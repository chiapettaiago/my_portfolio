# Script de exemplo para acesso remoto via PowerShell
# Este é um exemplo de como executar um script remotamente

# Para executar um script PowerShell de um link público, execute o seguinte comando no PowerShell:
# iex (Invoke-WebRequest -Uri "https://seusite.com/ps/TOKEN" -UseBasicParsing).Content

# Exemplo de script que busca informações do sistema
Write-Host "=== Informações do Sistema ===" -ForegroundColor Cyan
Write-Host "Nome do Computador: $env:COMPUTERNAME" -ForegroundColor Yellow
Write-Host "Usuário Atual: $env:USERNAME" -ForegroundColor Yellow

# Informações sobre o sistema operacional
$os = Get-WmiObject -Class Win32_OperatingSystem
Write-Host "`nSistema Operacional:" -ForegroundColor Cyan
Write-Host "Versão: $($os.Caption) $($os.Version)" -ForegroundColor White
Write-Host "Arquitetura: $($os.OSArchitecture)" -ForegroundColor White
Write-Host "Último Boot: $($os.ConvertToDateTime($os.LastBootUpTime))" -ForegroundColor White

# Verificar uso de memória
$memoryUsage = [math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory) / $os.TotalVisibleMemorySize * 100, 2)
Write-Host "`nUso de Memória: $memoryUsage%" -ForegroundColor $(if ($memoryUsage -gt 80) {'Red'} elseif ($memoryUsage -gt 60) {'Yellow'} else {'Green'})

# Informações sobre processador
$processor = Get-WmiObject -Class Win32_Processor
Write-Host "`nProcessador:" -ForegroundColor Cyan
Write-Host "Nome: $($processor.Name)" -ForegroundColor White
Write-Host "Núcleos: $($processor.NumberOfCores)" -ForegroundColor White
Write-Host "Threads: $($processor.NumberOfLogicalProcessors)" -ForegroundColor White

# Informações sobre disco
$disks = Get-WmiObject -Class Win32_LogicalDisk -Filter "DriveType=3"
Write-Host "`nDiscos:" -ForegroundColor Cyan
foreach ($disk in $disks) {
    $freeSpacePercentage = [math]::Round(($disk.FreeSpace / $disk.Size) * 100, 2)
    $color = if ($freeSpacePercentage -lt 10) {'Red'} elseif ($freeSpacePercentage -lt 20) {'Yellow'} else {'Green'}
    
    Write-Host "Drive $($disk.DeviceID)" -ForegroundColor White
    Write-Host "   Total: $([math]::Round($disk.Size / 1GB, 2)) GB" -ForegroundColor White
    Write-Host "   Livre: $([math]::Round($disk.FreeSpace / 1GB, 2)) GB" -ForegroundColor White
    Write-Host "   % Livre: $freeSpacePercentage%" -ForegroundColor $color
}

# Mostrar adaptadores de rede e endereços IP
Write-Host "`nAdaptadores de Rede:" -ForegroundColor Cyan
$adapters = Get-WmiObject -Class Win32_NetworkAdapterConfiguration -Filter "IPEnabled=True"
foreach ($adapter in $adapters) {
    Write-Host "$($adapter.Description)" -ForegroundColor White
    Write-Host "   MAC: $($adapter.MACAddress)" -ForegroundColor White
    Write-Host "   IP: $($adapter.IPAddress[0])" -ForegroundColor White
    Write-Host "   Máscara: $($adapter.IPSubnet[0])" -ForegroundColor White
    if ($adapter.DefaultIPGateway) {
        Write-Host "   Gateway: $($adapter.DefaultIPGateway[0])" -ForegroundColor White
    }
}

# Mostrar lista de serviços críticos em execução
$criticalServices = @("Winmgmt", "Dhcp", "Dnscache", "LanmanWorkstation", "LanmanServer")
Write-Host "`nServiços críticos:" -ForegroundColor Cyan
foreach ($service in $criticalServices) {
    $serviceObj = Get-Service -Name $service -ErrorAction SilentlyContinue
    if ($serviceObj) {
        $statusColor = if ($serviceObj.Status -eq 'Running') {'Green'} else {'Red'}
        Write-Host "$($serviceObj.DisplayName): $($serviceObj.Status)" -ForegroundColor $statusColor
    }
}

Write-Host "`n=== Script Executado com Sucesso ===" -ForegroundColor Green
