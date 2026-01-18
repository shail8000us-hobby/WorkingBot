/**
 * Brain Modules List Component
 *
 * Single Responsibility: Display discovered brain modules.
 *
 * Shows which files were scanned, line counts, metadata.
 * Auto-refreshes with parent component.
 */

import React, { useState, useEffect } from 'react';
import { Box, Typography, Card, CardContent, Chip, LinearProgress } from '@mui/material';
import { Code, FileText } from 'lucide-react';

const BrainModulesList = ({ flowData }) => {
  const [modules, setModules] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchModules = async () => {
      try {
        // Call brain analyzer API (same port as main WebUI)
        const response = await fetch('/api/brain/modules');
        const data = await response.json();
        if (data.success) {
          setModules(data.modules || []);
        }
      } catch (err) {
        console.error('Error fetching modules:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchModules();
    const interval = setInterval(fetchModules, 5000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return <LinearProgress />;
  }

  return (
    <Box>
      <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <Code className="w-5 h-5" />
        Discovered Brain Modules ({modules.length})
      </Typography>

      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
          gap: 2,
          mt: 2,
        }}
      >
        {modules.map((module, idx) => (
          <Card key={idx} variant="outlined">
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <FileText className="w-4 h-4" />
                <Typography variant="subtitle2" sx={{ fontWeight: 'bold' }}>
                  {module.name}
                </Typography>
              </Box>
              <Chip label={`${module.lines} lines`} size="small" sx={{ mr: 1 }} />
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
                {module.path}
              </Typography>
            </CardContent>
          </Card>
        ))}
      </Box>
    </Box>
  );
};

export default BrainModulesList;
