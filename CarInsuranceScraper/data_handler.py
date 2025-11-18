"""
Enhanced data handler for JSON and CSV output with comprehensive error handling
"""

import json
import pandas as pd
import os
from datetime import datetime
import re
from pathlib import Path
from typing import Optional, Dict, Any, List
from error_handler import ErrorHandler


class DataHandler:
    def __init__(self, output_folder, json_filename, csv_filename, error_handler: Optional[ErrorHandler] = None):
        """Initialize data handler with error handling"""
        self.output_folder = Path(output_folder)
        self.json_filename = json_filename
        self.csv_filename = csv_filename
        self.json_path = self.output_folder / json_filename
        self.csv_path = self.output_folder / csv_filename
        self.error_handler = error_handler or ErrorHandler(str(self.output_folder))
        
        # Create output folder if it doesn't exist with error handling
        try:
            self.output_folder.mkdir(parents=True, exist_ok=True)
            print(f"✓ Output folder ready: {self.output_folder}")
        except PermissionError as e:
            error_msg = f"Permission denied creating output folder: {self.output_folder}"
            self.error_handler.handle_file_error(e, str(self.output_folder), "create")
            raise
        except Exception as e:
            error_msg = f"Error creating output folder: {self.output_folder}"
            self.error_handler.handle_file_error(e, str(self.output_folder), "create")
            raise
    
    def save_to_json(self, data: Dict[str, Any], partial: bool = False) -> bool:
        """Save scraped data to JSON file with comprehensive error handling"""
        try:
            # Validate data structure
            if not isinstance(data, dict):
                raise ValueError(f"Data must be a dictionary, got {type(data)}")
            
            # Prepare data with metadata
            data_to_save = data.copy()
            if partial:
                data_to_save['_partial'] = True
                data_to_save['_saved_at'] = datetime.now().isoformat()
            
            # Load existing data if file exists
            existing_data = []
            if self.json_path.exists():
                try:
                    with open(self.json_path, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                    if not isinstance(existing_data, list):
                        # If file contains single object, convert to list
                        existing_data = [existing_data] if existing_data else []
                except json.JSONDecodeError as e:
                    # Backup corrupted file
                    backup_path = self.json_path.with_suffix('.json.backup')
                    try:
                        self.json_path.rename(backup_path)
                        self.error_handler.log_error(
                            "JSON_CORRUPTION", 
                            f"Corrupted JSON file backed up to {backup_path}. Starting fresh.",
                            e
                        )
                        existing_data = []
                    except Exception as backup_error:
                        self.error_handler.handle_file_error(backup_error, str(backup_path), "backup")
                        # Continue with empty list
                        existing_data = []
                except PermissionError as e:
                    self.error_handler.handle_file_error(e, str(self.json_path), "read")
                    return False
                except Exception as e:
                    self.error_handler.handle_file_error(e, str(self.json_path), "read")
                    return False
            
            # Append new data
            existing_data.append(data_to_save)
            
            # Write to temporary file first, then rename (atomic operation)
            temp_path = self.json_path.with_suffix('.json.tmp')
            try:
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(existing_data, f, indent=4, ensure_ascii=False)
                
                # Atomic rename
                temp_path.replace(self.json_path)
                
                status_msg = "partial data" if partial else "data"
                print(f"✓ {status_msg.capitalize()} saved to JSON: {self.json_path}")
                return True
                
            except PermissionError as e:
                self.error_handler.handle_file_error(e, str(temp_path), "write")
                # Try to clean up temp file
                try:
                    if temp_path.exists():
                        temp_path.unlink()
                except Exception:
                    pass
                return False
            except OSError as e:
                # Disk full, no space, etc.
                self.error_handler.handle_file_error(e, str(temp_path), "write")
                try:
                    if temp_path.exists():
                        temp_path.unlink()
                except Exception:
                    pass
                return False
            except Exception as e:
                self.error_handler.handle_file_error(e, str(temp_path), "write")
                try:
                    if temp_path.exists():
                        temp_path.unlink()
                except Exception:
                    pass
                return False
                
        except ValueError as e:
            self.error_handler.log_error("DATA_VALIDATION", f"Invalid data structure: {str(e)}", e)
            return False
        except Exception as e:
            self.error_handler.handle_file_error(e, str(self.json_path), "save")
            return False
    
    def convert_to_structured_csv(self, json_data: List[Dict[str, Any]]) -> Optional[pd.DataFrame]:
        """Convert JSON data to structured CSV format with error handling"""
        try:
            if not json_data:
                print("⚠️  No data to convert")
                return None
            
            rows = []
            
            for entry_idx, entry in enumerate(json_data):
                try:
                    timestamp = entry.get('timestamp', '')
                    car_number = entry.get('car_number', '')
                    page_url = entry.get('page_url', '')
                    
                    # Extract city from car number (first 2 chars)
                    city = car_number[:2] if car_number else ''
                    
                    variants = entry.get('variants', [])
                    if not variants:
                        print(f"⚠️  Entry {entry_idx + 1} has no variants, skipping...")
                        continue
                    
                    for variant in variants:
                        try:
                            row = {
                                'timestamp': timestamp,
                                'city': city,
                                'make': 'Unknown',  # Extract from page if available
                                'model': 'Unknown',  # Extract from page if available
                                'year': 'Unknown',  # Extract from page if available
                                'car_number': car_number,
                                'variant_number': variant.get('variant_number', 1),
                                'insurer': variant.get('insurer', 'GoDigit'),
                                'idv': self._extract_number(variant.get('idv', '0')),
                                'ncb': variant.get('ncb', '0%'),
                                'actual_premium': self._extract_number(variant.get('actual_premium', '0')),
                                'discounted_premium': self._extract_number(variant.get('discounted_premium', '0')),
                                'gst_info': variant.get('gst_info', ''),
                                'addons': ', '.join(variant.get('addons', [])),
                                'url': page_url
                            }
                            
                            # Calculate delta and percentage reduction
                            try:
                                actual = float(self._extract_number(variant.get('actual_premium', '0')))
                                discounted = float(self._extract_number(variant.get('discounted_premium', '0')))
                                
                                row['delta'] = actual - discounted
                                row['ncb_reduction_percent'] = ((actual - discounted) / actual * 100) if actual > 0 else 0
                            except (ValueError, ZeroDivisionError) as e:
                                self.error_handler.log_error("CALCULATION_ERROR", f"Error calculating premium delta: {str(e)}")
                                row['delta'] = 0
                                row['ncb_reduction_percent'] = 0
                            
                            rows.append(row)
                        except Exception as e:
                            self.error_handler.log_error("VARIANT_CONVERSION", f"Error converting variant: {str(e)}", e)
                            continue
                
                except Exception as e:
                    self.error_handler.log_error("ENTRY_CONVERSION", f"Error converting entry {entry_idx + 1}: {str(e)}", e)
                    continue
            
            if not rows:
                print("⚠️  No valid rows to write to CSV")
                return None
            
            # Create DataFrame
            try:
                df = pd.DataFrame(rows)
            except Exception as e:
                self.error_handler.log_error("DATAFRAME_CREATION", f"Error creating DataFrame: {str(e)}", e)
                return None
            
            # Write to CSV with error handling
            temp_csv_path = self.csv_path.with_suffix('.csv.tmp')
            try:
                df.to_csv(temp_csv_path, index=False, encoding='utf-8')
                # Atomic rename
                temp_csv_path.replace(self.csv_path)
                print(f"✓ Data saved to CSV: {self.csv_path}")
                return df
            except PermissionError as e:
                self.error_handler.handle_file_error(e, str(temp_csv_path), "write")
                try:
                    if temp_csv_path.exists():
                        temp_csv_path.unlink()
                except Exception:
                    pass
                return None
            except OSError as e:
                self.error_handler.handle_file_error(e, str(temp_csv_path), "write")
                try:
                    if temp_csv_path.exists():
                        temp_csv_path.unlink()
                except Exception:
                    pass
                return None
            except Exception as e:
                self.error_handler.handle_file_error(e, str(temp_csv_path), "write")
                try:
                    if temp_csv_path.exists():
                        temp_csv_path.unlink()
                except Exception:
                    pass
                return None
                
        except Exception as e:
            self.error_handler.log_error("CSV_CONVERSION", f"Unexpected error converting to CSV: {str(e)}", e)
            return None
    
    def _extract_number(self, text: Any) -> str:
        """Extract numeric value from text with error handling"""
        if not text:
            return '0'
        try:
            # Remove currency symbols and commas
            cleaned = re.sub(r'[₹,\s]', '', str(text))
            # Extract first number found
            match = re.search(r'[\d.]+', cleaned)
            return match.group(0) if match else '0'
        except Exception as e:
            self.error_handler.log_error("NUMBER_EXTRACTION", f"Error extracting number from '{text}': {str(e)}")
            return '0'
    
    def load_and_convert(self) -> Optional[pd.DataFrame]:
        """Load JSON and convert to CSV with error handling"""
        try:
            if not self.json_path.exists():
                print(f"⚠️  JSON file not found: {self.json_path}")
                return None
            
            # Check file permissions
            if not os.access(self.json_path, os.R_OK):
                raise PermissionError(f"No read permission for {self.json_path}")
            
            try:
                with open(self.json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if not data:
                    print("⚠️  JSON file is empty")
                    return None
                
                # Ensure data is a list
                if not isinstance(data, list):
                    data = [data]
                
                return self.convert_to_structured_csv(data)
                
            except json.JSONDecodeError as e:
                self.error_handler.handle_file_error(e, str(self.json_path), "read")
                print(f"✗ Failed to parse JSON file: {str(e)}")
                return None
            except PermissionError as e:
                self.error_handler.handle_file_error(e, str(self.json_path), "read")
                return None
            except Exception as e:
                self.error_handler.handle_file_error(e, str(self.json_path), "read")
                return None
                
        except Exception as e:
            self.error_handler.log_error("LOAD_ERROR", f"Unexpected error loading JSON: {str(e)}", e)
            return None
    
    def display_summary(self) -> Optional[pd.DataFrame]:
        """Display summary of scraped data with error handling"""
        try:
            if not self.csv_path.exists():
                print(f"⚠️  CSV file not found: {self.csv_path}")
                return None
            
            # Check file permissions
            if not os.access(self.csv_path, os.R_OK):
                raise PermissionError(f"No read permission for {self.csv_path}")
            
            try:
                df = pd.read_csv(self.csv_path)
                
                if df.empty:
                    print("⚠️  CSV file is empty")
                    return None
                
                print("\n" + "="*60)
                print("DATA SUMMARY")
                print("="*60)
                print(f"Total records: {len(df)}")
                
                if 'insurer' in df.columns:
                    print(f"\nInsurers: {df['insurer'].unique()}")
                
                if 'idv' in df.columns:
                    try:
                        avg_idv = df['idv'].astype(float).mean()
                        print(f"\nAverage IDV: ₹{avg_idv:,.2f}")
                    except Exception as e:
                        print(f"\n⚠️  Could not calculate average IDV: {str(e)}")
                
                if 'discounted_premium' in df.columns:
                    try:
                        avg_premium = df['discounted_premium'].astype(float).mean()
                        print(f"Average Premium: ₹{avg_premium:,.2f}")
                    except Exception as e:
                        print(f"⚠️  Could not calculate average premium: {str(e)}")
                
                if 'delta' in df.columns:
                    try:
                        avg_delta = df['delta'].mean()
                        print(f"Average NCB Savings: ₹{avg_delta:,.2f}")
                    except Exception as e:
                        print(f"⚠️  Could not calculate average delta: {str(e)}")
                
                if 'ncb_reduction_percent' in df.columns:
                    try:
                        avg_reduction = df['ncb_reduction_percent'].mean()
                        print(f"Average NCB Reduction: {avg_reduction:.2f}%")
                    except Exception as e:
                        print(f"⚠️  Could not calculate average reduction: {str(e)}")
                
                print("\n--- Latest Entry ---")
                try:
                    print(df.tail(1).to_string(index=False))
                except Exception as e:
                    print(f"⚠️  Could not display latest entry: {str(e)}")
                
                return df
                
            except pd.errors.EmptyDataError:
                print("⚠️  CSV file is empty")
                return None
            except pd.errors.ParserError as e:
                self.error_handler.handle_file_error(e, str(self.csv_path), "parse")
                print(f"✗ Failed to parse CSV file: {str(e)}")
                return None
            except PermissionError as e:
                self.error_handler.handle_file_error(e, str(self.csv_path), "read")
                return None
            except Exception as e:
                self.error_handler.handle_file_error(e, str(self.csv_path), "read")
                return None
                
        except Exception as e:
            self.error_handler.log_error("SUMMARY_ERROR", f"Unexpected error displaying summary: {str(e)}", e)
            return None
