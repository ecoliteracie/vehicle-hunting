# Builds data/used.json for the site's "Used" page: Texas Toyota of Grapevine listings
# (valuation/data/used/*.csv, source = Texas Toyota of Grapevine) merged with the manual
# Kelley Blue Book lookups in valuation/data/_kbb_values.csv (joined by stock number).
# Run from the repo root:  powershell -File valuation/scripts/build_used_json.ps1
$ErrorActionPreference = 'Stop'
$kbb = @(Import-Csv valuation/data/_kbb_values.csv)
$cars = @{}
foreach ($f in Get-ChildItem valuation/data/used/toyota_*.csv) {
  foreach ($r in Import-Csv $f.FullName) {
    if ($r.source -ne 'Texas Toyota of Grapevine') { continue }
    $stock = [regex]::Match($r.notes, 'stock (\w+)').Groups[1].Value
    $cars[$stock] = [ordered]@{
      stock = $stock; vehicleId = $r.vehicle_id; model = $r.model; trim = $r.trim; year = [int]$r.year
      mileage = [int]$r.mileage; askingPrice = [int]$r.price; status = $r.status
      powertrain = $r.powertrain; dateSeen = $r.date_collected; kbb = $null; note = $null
    }
  }
}
foreach ($k in $kbb) {
  $n = { param($v) if ($v -eq '') { $null } else { [int]$v } }
  $obj = [ordered]@{
    tradeLow = & $n $k.kbb_trade_low; tradeHigh = & $n $k.kbb_trade_high
    privateLow = & $n $k.kbb_private_low; privateHigh = & $n $k.kbb_private_high
    checked = $k.date_recorded
  }
  if (-not $cars.ContainsKey($k.stock_number)) {
    $cars[$k.stock_number] = [ordered]@{
      stock = $k.stock_number; vehicleId = $null; model = $k.model; trim = $k.trim; year = [int]$k.year
      mileage = [int]$k.mileage; askingPrice = $null; status = 'available'; powertrain = $null
      dateSeen = $k.date_recorded; kbb = $null; note = $null }
  }
  $cars[$k.stock_number].kbb = $obj
  if ($k.notes -match 'trim NOT stated') { $cars[$k.stock_number].note = 'Trim assumed' }
}
$list = $cars.Values | Sort-Object @{e={$_.model}}, @{e={$_.kbb -eq $null}}, @{e={$_.askingPrice}}
$out = [ordered]@{
  dealer = 'Texas Toyota of Grapevine'; asOf = '2026-10-17'
  note = 'Dealer asking prices include the $225 doc fee per the dealer. KBB values are manual lookups on the date shown.'
  cars = @($list)
}
[IO.File]::WriteAllText("$PWD/data/used.json", ($out | ConvertTo-Json -Depth 6), (New-Object Text.UTF8Encoding($false)))
"{0} cars, {1} with KBB" -f $list.Count, @($list | ? kbb).Count
