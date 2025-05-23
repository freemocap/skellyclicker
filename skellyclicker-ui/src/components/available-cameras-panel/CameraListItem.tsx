// skellyclicker-ui/src/components/available-cameras-panel/CameraListItem.tsx
import {Box, Checkbox, IconButton, ListItem, ListItemIcon, ListItemText, Typography, useTheme} from "@mui/material";
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import * as React from "react";
import {CameraDevice} from "@/store/slices/cameras-slices/camera-types";

interface CameraListItemProps {
    camera: CameraDevice;
    isLast: boolean;
    isConfigExpanded: boolean;
    onToggleSelect: () => void;
    onToggleConfig: () => void;
}

export const CameraListItem: React.FC<CameraListItemProps> = ({
                                                                  camera,
                                                                  isLast,
                                                                  isConfigExpanded,
                                                                  onToggleSelect,
                                                                  onToggleConfig
                                                              }) => {
    // Move useTheme() inside the component body
    const theme = useTheme();

    return (
        <ListItem
            sx={{
                '&:hover': {
                    bgcolor: 'action.hover',
                },
                borderBottom: isLast ? 0 : 1,
                borderColor: 'divider',
            }}
        >
            <ListItemIcon>
                <Checkbox
                    edge="start"
                    checked={camera.selected || false}
                    onChange={onToggleSelect}
                    color={theme.palette.primary.main as any}
                />
            </ListItemIcon>
            <ListItemText
                primary={
                    <Box sx={{display: 'flex', alignItems: 'center'}}>
                        <Typography
                            component="span"
                            variant="body2"
                            color={theme.palette.text.primary}
                            sx={{mr: 1, fontWeight: 600}}
                        >
                            Camera {camera.index}
                        </Typography>
                        <Typography
                            component="span"
                            variant="body2"
                            color={theme.palette.text.secondary}
                        >
                            {`${camera.label}, id: ${camera.cameraId}` || `Unknown Device ${camera.index}`}
                        </Typography>
                    </Box>
                }
            />
            {camera.selected && (
                <IconButton
                    size="small"
                    onClick={onToggleConfig}
                >
                    {isConfigExpanded
                        ? <KeyboardArrowUpIcon/>
                        : <KeyboardArrowDownIcon/>}
                </IconButton>
            )}
        </ListItem>
    );
};
