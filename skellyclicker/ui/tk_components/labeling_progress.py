import tkinter as tk
from math import ceil

class LabelingProgress(tk.Frame):
    def __init__(self, total_rows: int, labeled_rows: list[int] | None = None, master=None, width=400, height=50):
        super().__init__(master)
        self.master = master
        
        # Create canvas
        self.canvas = tk.Canvas(self, width=width, height=height, bg='white', highlightthickness=0)
        self.canvas.pack()
        
        # Store dimensions
        self.width = width
        self.height = height
        
        # Colors
        self.background_color = '#f0f0f0'
        self.indicator_color = '#2196F3'  # Blue
        self.grid_color = '#e0e0e0'
        
        # Initialize state
        self.total_rows = total_rows
        if labeled_rows is None:
            labeled_rows = []
        self.labeled_rows = labeled_rows
        
        # Draw initial state
        self._draw_rectangle(0, [])

    def reset(self, total_rows: int, labeled_rows: list[int] | None = None):
        """Reset the progress indicator"""
        self.total_rows = total_rows
        if labeled_rows is None:
            labeled_rows = []
        self.labeled_rows = labeled_rows
        self._draw_rectangle(total_rows, labeled_rows) 

    def update(self, total_rows: int, labeled_rows: list[int]):
        """Update the progress indicator with new labeled rows"""
        self.total_rows = total_rows
        self.labeled_rows = labeled_rows
        self._draw_rectangle(self.total_rows, self.labeled_rows)
    
    def _draw_rectangle(self, total_rows: int, labeled_rows: list[int] | None = None):
        """Draw the rectangular progress indicator"""
        # Clear canvas
        self.canvas.delete("all")

        if labeled_rows is None:
            labeled_rows = []
        
        # Store parameters
        self.total_rows = total_rows
        self.labeled_rows = labeled_rows
        
        # Draw background rectangle
        self.canvas.create_rectangle(10, 10, self.width-10, self.height-10,
                                   fill=self.background_color)
        
        # Calculate spacing for indicators
        if total_rows > 0:
            spacing = (self.width - 20) / max(total_rows, 1)
            
            # Add grid lines for reference
            for i in range(0, int(self.width-20), 50):  # Grid every 50 pixels
                x = 10 + i
                self.canvas.create_line(x, 10, x, self.height-10,
                                      fill=self.grid_color, dash=(2,2))
            
            # Draw labeled rows indicators
            for row in sorted(labeled_rows):
                position = int((row / total_rows) * (self.width - 20)) + 10
                self.canvas.create_line(position, 10, position, self.height-10,
                                       fill=self.indicator_color, width=2)

if __name__ == "__main__":
    # Create demo window
    root = tk.Tk()
    app = LabelingProgress(root)
    app.pack()

    # Simulate labeling progress
    def update_progress():
        current_labeled = len(app.labeled_rows)
        if current_labeled < 100:  # Simulate 100 total rows
            app.labeled_rows.append(current_labeled)
            app.update(app.labeled_rows)
            root.after(500, update_progress)

    update_progress()
    root.mainloop()