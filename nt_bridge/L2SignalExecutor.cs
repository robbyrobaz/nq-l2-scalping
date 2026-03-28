// L2SignalExecutor.cs
// Place in: C:\Users\hartw\Documents\NinjaTrader 8\bin\Custom\AddOns\

using System;
using System.IO;
using System.Windows;
using System.Windows.Media;
using NinjaTrader.Cbi;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Tools;
using NinjaTrader.NinjaScript;
using Newtonsoft.Json;

namespace NinjaTrader.NinjaScript.AddOns
{
    public class L2SignalExecutor : NinjaTrader.NinjaScript.AddOnBase
    {
        private string signalFilePath = @"\\WSLHOST$\Ubuntu\home\rob\.openclaw\workspace\nq-l2-scalping\nt_bridge\signal_output.json";
        private string positionFilePath = @"C:\Users\hartw\Documents\NinjaTrader ML Bridge\position_state.json";
        private string executionsFilePath = @"C:\Users\hartw\Documents\NinjaTrader ML Bridge\executions.csv";
        
        private System.Windows.Threading.DispatcherTimer timer;
        private DateTime lastSignalTime = DateTime.MinValue;
        private Account simAccount;
        
        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "L2 Signal Executor - Reads signals from Omen, executes via ATI";
                Name = "L2SignalExecutor";
            }
            else if (State == State.Terminated)
            {
                if (timer != null)
                {
                    timer.Stop();
                    timer = null;
                }
            }
        }

        protected override void OnStartUp()
        {
            // Find SimL2020 account
            lock (Account.All)
            {
                foreach (Account acc in Account.All)
                {
                    if (acc.Name == "SimL2020")
                    {
                        simAccount = acc;
                        Print("✅ Found SimL2020 account");
                        break;
                    }
                }
            }
            
            if (simAccount == null)
            {
                Print("❌ SimL2020 account not found!");
                return;
            }
            
            // Start timer - check for signals every 5 seconds
            timer = new System.Windows.Threading.DispatcherTimer();
            timer.Interval = TimeSpan.FromSeconds(5);
            timer.Tick += OnTimerTick;
            timer.Start();
            
            Print("✅ L2 Signal Executor started");
            Print($"   Watching: {signalFilePath}");
        }

        private void OnTimerTick(object sender, EventArgs e)
        {
            try
            {
                // Check if signal file exists
                if (!File.Exists(signalFilePath))
                    return;
                
                // Read signal
                string json = File.ReadAllText(signalFilePath);
                dynamic signal = JsonConvert.DeserializeObject(json);
                
                // Parse timestamp
                DateTime signalTime = DateTime.Parse(signal.timestamp.ToString());
                
                // Skip if we already processed this signal
                if (signalTime <= lastSignalTime)
                    return;
                
                lastSignalTime = signalTime;
                
                // Skip if dry_run is true
                if (signal.dry_run == true)
                {
                    Print($"⏭️  Dry run signal skipped: {signal.direction} @ {signal.entry_price}");
                    return;
                }
                
                // Execute signal
                string direction = signal.direction.ToString();
                double entryPrice = (double)signal.entry_price;
                double tpPrice = (double)signal.tp_price;
                double slPrice = (double)signal.sl_price;
                int contracts = (int)signal.contracts;
                
                Print($"🎯 EXECUTING SIGNAL: {direction.ToUpper()} x{contracts}");
                Print($"   Entry: {entryPrice:F2}");
                Print($"   TP: {tpPrice:F2}");
                Print($"   SL: {slPrice:F2}");
                
                // Place market order
                Instrument nq = Instrument.GetInstrument("NQ 03-26");  // Update month as needed
                
                Order entry = simAccount.CreateOrder(
                    nq,
                    direction == "long" ? OrderAction.Buy : OrderAction.Sell,
                    OrderType.Market,
                    OrderEntry.Managed,
                    TimeInForce.Day,
                    contracts,
                    0,
                    0,
                    string.Empty,
                    "L2_Strategy_020",
                    null,
                    null
                );
                
                simAccount.Submit(new[] { entry });
                
                // Log execution
                LogExecution(direction, entryPrice, tpPrice, slPrice, contracts);
                
                Print("✅ Order submitted to SimL2020");
                
            }
            catch (Exception ex)
            {
                Print($"❌ Error: {ex.Message}");
            }
        }
        
        private void LogExecution(string direction, double entry, double tp, double sl, int contracts)
        {
            try
            {
                // Write to executions.csv
                string line = $"{DateTime.Now:yyyy-MM-dd HH:mm:ss},strategy_020,{direction},{entry:F2},{tp:F2},{sl:F2},{contracts}";
                File.AppendAllText(executionsFilePath, line + Environment.NewLine);
                
                // Update position_state.json
                var position = new {
                    position = direction == "long" ? "Long" : "Short",
                    entry_price = entry,
                    unrealized_pnl = 0.0,
                    quantity = contracts,
                    instrument = "NQ 03-26",
                    account = "SimL2020",
                    timestamp = DateTime.Now.ToString("o")
                };
                
                string posJson = JsonConvert.SerializeObject(position, Formatting.Indented);
                File.WriteAllText(positionFilePath, posJson);
                
            }
            catch (Exception ex)
            {
                Print($"⚠️  Logging error: {ex.Message}");
            }
        }
    }
}
