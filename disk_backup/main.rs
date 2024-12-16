use std::fs::{File, OpenOptions};
use std::io::{self, Read, Seek, SeekFrom, Write};
use std::path::Path;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;
use thiserror::Error;

#[derive(Error, Debug)]
pub enum CloneError {
    #[error("IO error: {0}")]
    Io(#[from] io::Error),
    #[error("Source disk is larger than destination")]
    DiskSizeMismatch,
    #[error("Invalid disk layout")]
    InvalidLayout,
    #[error("Bad sector detected at offset {0}")]
    BadSector(u64),
}

pub struct DiskInfo {
    pub total_size: u64,
    pub used_space: u64,
    pub sector_size: u32,
}

#[derive(Clone, Copy)]
pub enum CloneMode {
    /// Copies disk sector by sector
    SectorBySector,
    /// Only copies used sectors
    SmartClone,
    /// Automatically resizes partitions to fit destination disk
    AutoFit,
}

pub struct DiskCloner {
    buffer_size: usize,
    mode: CloneMode,
    progress: Arc<AtomicU64>,
}

impl DiskCloner {
    pub fn new(mode: CloneMode) -> Self {
        Self {
            buffer_size: 1024 * 1024, // 1MB buffer
            mode,
            progress: Arc::new(AtomicU64::new(0)),
        }
    }

    /// Gets progress as a percentage
    pub fn get_progress(&self) -> f64 {
        let progress = self.progress.load(Ordering::Relaxed);
        progress as f64 / 100.0
    }

    /// Clones source disk to destination disk
    pub fn clone_disk<P: AsRef<Path>>(
        &self,
        source_path: P,
        dest_path: P,
    ) -> Result<(), CloneError> {
        let source_info = self.get_disk_info(source_path.as_ref())?;
        let dest_info = self.get_disk_info(dest_path.as_ref())?;

        // Verify disk size compatibility
        if source_info.total_size > dest_info.total_size && self.mode != CloneMode::SmartClone {
            return Err(CloneError::DiskSizeMismatch);
        }

        let mut source = File::open(source_path)?;
        let mut dest = OpenOptions::new()
            .write(true)
            .create(true)
            .open(dest_path)?;

        match self.mode {
            CloneMode::SectorBySector => {
                self.clone_sector_by_sector(&mut source, &mut dest, source_info.total_size)?
            }
            CloneMode::SmartClone => {
                self.smart_clone(&mut source, &mut dest, &source_info)?
            }
            CloneMode::AutoFit => {
                self.auto_fit_clone(&mut source, &mut dest, &source_info, &dest_info)?
            }
        }

        Ok(())
    }

    fn clone_sector_by_sector(
        &self,
        source: &mut File,
        dest: &mut File,
        total_size: u64,
    ) -> Result<(), CloneError> {
        let mut buffer = vec![0u8; self.buffer_size];
        let mut bytes_copied = 0u64;

        while bytes_copied < total_size {
            let bytes_to_read = std::cmp::min(
                self.buffer_size as u64,
                total_size - bytes_copied,
            ) as usize;

            match source.read(&mut buffer[..bytes_to_read]) {
                Ok(0) => break, // EOF
                Ok(n) => {
                    dest.write_all(&buffer[..n])?;
                    bytes_copied += n as u64;
                    self.update_progress(bytes_copied, total_size);
                }
                Err(e) => {
                    if e.kind() == io::ErrorKind::InvalidData {
                        // Potential bad sector detected
                        return Err(CloneError::BadSector(bytes_copied));
                    }
                    return Err(e.into());
                }
            }
        }

        Ok(())
    }

    fn smart_clone(
        &self,
        source: &mut File,
        dest: &mut File,
        source_info: &DiskInfo,
    ) -> Result<(), CloneError> {
        // Only copy used sectors
        let mut buffer = vec![0u8; self.buffer_size];
        let mut bytes_copied = 0u64;

        while bytes_copied < source_info.used_space {
            let bytes_to_read = std::cmp::min(
                self.buffer_size as u64,
                source_info.used_space - bytes_copied,
            ) as usize;

            match source.read(&mut buffer[..bytes_to_read]) {
                Ok(0) => break,
                Ok(n) => {
                    dest.write_all(&buffer[..n])?;
                    bytes_copied += n as u64;
                    self.update_progress(bytes_copied, source_info.used_space);
                }
                Err(e) => return Err(e.into()),
            }
        }

        Ok(())
    }

    fn auto_fit_clone(
        &self,
        source: &mut File,
        dest: &mut File,
        source_info: &DiskInfo,
        dest_info: &DiskInfo,
    ) -> Result<(), CloneError> {
        // Calculate scaling factor for partition sizes
        let scale_factor = dest_info.total_size as f64 / source_info.total_size as f64;

        // First copy all data
        self.smart_clone(source, dest, source_info)?;

        // Then adjust partition table
        self.adjust_partition_table(dest, scale_factor)?;

        Ok(())
    }

    fn adjust_partition_table(
        &self,
        dest: &mut File,
        scale_factor: f64,
    ) -> Result<(), CloneError> {
        // Read partition table
        dest.seek(SeekFrom::Start(0x1BE))?; // Standard MBR partition table offset
        let mut table = [0u8; 64]; // 4 partition entries of 16 bytes each
        dest.read_exact(&mut table)?;

        // Adjust each partition entry
        for chunk in table.chunks_mut(16) {
            if chunk[4] != 0 { // If partition type is not empty
                let start_sector = u32::from_le_bytes([chunk[8], chunk[9], chunk[10], chunk[11]]);
                let length_sectors = u32::from_le_bytes([chunk[12], chunk[13], chunk[14], chunk[15]]);

                // Scale the partition size
                let new_length = (length_sectors as f64 * scale_factor) as u32;
                chunk[12..16].copy_from_slice(&new_length.to_le_bytes());
            }
        }

        // Write back adjusted partition table
        dest.seek(SeekFrom::Start(0x1BE))?;
        dest.write_all(&table)?;

        Ok(())
    }

    fn get_disk_info(&self, path: &Path) -> Result<DiskInfo, CloneError> {
        let file = File::open(path)?;
        let metadata = file.metadata()?;

        Ok(DiskInfo {
            total_size: metadata.len(),
            used_space: metadata.len(), // In a real implementation, this would need to read filesystem metadata
            sector_size: 512, // Standard sector size, would need to query actual hardware
        })
    }

    fn update_progress(&self, current: u64, total: u64) {
        let percentage = (current as f64 / total as f64 * 100.0) as u64;
        self.progress.store(percentage, Ordering::Relaxed);
    }
}

// Example usage
fn main() -> Result<(), CloneError> {
    let cloner = DiskCloner::new(CloneMode::AutoFit);
    
    println!("Starting disk clone...");
    
    cloner.clone_disk("/dev/sda", "/dev/sdb")?;
    
    println!("Clone completed successfully!");
    println!("Final progress: {}%", cloner.get_progress());
    
    Ok(())
}
