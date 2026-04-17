const fs = require('fs');

const path = '/Users/ssr/Projects/WorkingBot/webui/frontend/src/App.js';
let src = fs.readFileSync(path, 'utf8');

src = src.replace(/\{isMobile \? \([\s\S]*?\) : \(/m, 
`{isMobile ? (
                    <>
                      <Route path="/dashboard" element={<MobileDashboard socket={socket} />} />
                      <Route element={<MobileMMMLayout socket={socket} />}>
                        <Route path="/mmm" element={<MobileMMMView socket={socket} />} />
                        <Route path="/control" element={<Navigate to="/mmm" replace />} />
                        <Route
                          path="/config"
                          element={(
                            <MobileConfig
                              config={config}
                              isMobile={isMobile}
                              handleConfigUpdate={handleConfigUpdate}
                              busy={busy}
                            />
                          )}
                        />
                        <Route path="/risk" element={<MobileRiskRoute botStatus={botStatus} config={config} />} />
                        <Route path="/monitoring" element={<MobileMonitoring botStatus={botStatus} />} />
                      </Route>
                    </>
                  ) : (`
);

fs.writeFileSync(path, src);
console.log("App.js patched successfully for purely restoring MMM Mobile route");
